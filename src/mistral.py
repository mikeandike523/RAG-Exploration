from dataclasses import dataclass
from typing import List, Literal, Optional, TypedDict, Union
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
import pynvml
import psutil
from collections import defaultdict
from termcolor import colored
from torch.nn.utils.rnn import pad_sequence
import re

# Static constants
DEFAULT_GPU_HEADROOM_PCT = 0.15          # reserve 15% of each GPU for activations, cache, allocator
DEFAULT_OS_RAM_RESERVE_GB = 4           # reserve 4GB of system RAM for OS/processes

# Pre-init NVML once at module load
try:
    pynvml.nvmlInit()
except Exception:
    pass

MODEL_ID = "mistralai/Mistral-Nemo-Instruct-2407"

bnb_config_8bit = BitsAndBytesConfig(
    load_in_4bit=False,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

bnb_config_4bit = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

@dataclass
class Message:
    role: Literal["user", "assistant", "system"]
    content: str

class CompletionRequest(TypedDict):
    messages: List[Message]
    top_p: Optional[float]
    max_tokens: Optional[int]
    temperature: Optional[float]

class BatchCompletionRequest(TypedDict):
    conversations: List[List[Message]]
    top_p: Optional[float]
    max_tokens: Optional[int]
    temperature: Optional[float]

@dataclass
class OutOfTokensError(Exception):
    budget: int
    total_tokens: int

@dataclass
class OutOfMemoryError(Exception):
    device_or_devices: Union[str, List[str]]
    used: dict
    requested: dict

@dataclass
class UnfinishedResponseError(Exception):
    max_new_tokens: int
    generation: str

class Mistral:
    def __init__(
        self,
        model_id: str = MODEL_ID,
        quantization: Optional[Literal["8bit", "4bit"]] = None,
        default_temperature: float = 0.6,
        default_top_p: float = 0.9,
        pad_margin: int = 2,
        device_ids: Optional[Union[int, List[int]]] = None,
        gpu_headroom_pct: float = DEFAULT_GPU_HEADROOM_PCT,
        ram_budget_gb: Optional[int] = None,
    ):
        """
        Initialize Mistral model with explicit GPU and CPU budgeting.

        device_ids:
          - None: use all available GPUs
          - int: use specified GPU
          - List[int]: use specified GPUs

        gpu_headroom_pct: fraction of each GPU to reserve for activations and overhead
        ram_budget_gb: max GB to use on CPU RAM; None = full system RAM minus OS reserve
        """
        # Detect GPUs
        total_gpus = torch.cuda.device_count()
        if total_gpus == 0:
            raise RuntimeError("No CUDA-capable GPUs detected. Cannot initialize model on GPU.")
        if device_ids is None:
            ids = list(range(total_gpus))
        else:
            ids = [device_ids] if isinstance(device_ids, int) else list(device_ids)
            invalid = [i for i in ids if i < 0 or i >= total_gpus]
            if invalid:
                raise ValueError(f"Invalid device IDs: {invalid}")

        # Build max_memory budget dict with integer GPU keys
        budgets = {}
        for idx in ids:
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            total_gb = pynvml.nvmlDeviceGetMemoryInfo(handle).total // (1024**3)
            headroom = max(1, int(total_gb * gpu_headroom_pct))
            avail = total_gb - headroom
            if avail <= 0:
                raise ValueError(
                    f"Computed GPU headroom {headroom}GB >= GPU {idx} total {total_gb}GB"
                )
            # Use integer keys to match Accelerate's expected device identifiers
            budgets[idx] = f"{avail}GB"

        # CPU RAM budget
        system_ram_gb = psutil.virtual_memory().total // (1024**3)
        if ram_budget_gb is None:
            cpu_budget = max(0, system_ram_gb - DEFAULT_OS_RAM_RESERVE_GB)
        else:
            cpu_budget = min(ram_budget_gb, system_ram_gb - DEFAULT_OS_RAM_RESERVE_GB)
        budgets["cpu"] = f"{cpu_budget}GB"

        # Load tokenizer and model with explicit budgets
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        load_kwargs = {
            "device_map": "auto",
            "torch_dtype": torch.bfloat16,
            "max_memory": budgets,
        }
        if quantization:
            qconfig = bnb_config_4bit if quantization == "4bit" else bnb_config_8bit
            load_kwargs["quantization_config"] = qconfig
        self.model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)

        # Store settings
        self.default_temperature = default_temperature
        self.default_top_p = default_top_p
        self.pad_margin = pad_margin
        cfg = self.model.config
        self.hard_limit = getattr(cfg, "max_position_embeddings", None)
        self.sliding_window = getattr(cfg, "sliding_window", None)

    def _compute_max_new_tokens(self, input_ids_len: int) -> int:
        budget = self.sliding_window or self.hard_limit
        if budget is None:
            raise ValueError("Model configuration missing context limits.")
        return max(0, budget - input_ids_len - self.pad_margin)

    def _batch_generate(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        max_tokens: int,
        top_p: float,
        temperature: float,
    ) -> torch.Tensor:
        return self.model.generate(
            input_ids,
            attention_mask=attention_mask,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_tokens,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )

    def report_memory_usage(self) -> None:
        try:
            for i in range(torch.cuda.device_count()):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                reserved = torch.cuda.memory_reserved(i) / 2**30
                allocated = torch.cuda.memory_allocated(i) / 2**30
                print(
                    f"GPU {i}: driver_used={mem.used/2**30:.2f}GB, "
                    f"reserved={reserved:.2f}GB, allocated={allocated:.2f}GB"
                )
            self._report_model_shard_distribution()
        except Exception as e:
            print(colored(f"Memory report error: {e}", "red"))

    def _report_model_shard_distribution(self) -> None:
        device_params = defaultdict(lambda: {"count": 0, "bytes": 0})
        for _, p in self.model.named_parameters():
            dev = str(p.device)
            device_params[dev]["count"] += p.numel()
            device_params[dev]["bytes"] += p.numel() * p.element_size()
        for dev, s in device_params.items():
            print(f"{dev}: {s['bytes']/2**30:.2f}GB in {s['count']} params")

    def completion(self, payload: CompletionRequest) -> str:
        batch = BatchCompletionRequest(
            conversations=[payload["messages"]],
            top_p=payload.get("top_p"),
            max_tokens=payload.get("max_tokens"),
            temperature=payload.get("temperature"),
        )
        return self.batch_completion(batch)[0]

    def batch_completion(self, payload: BatchCompletionRequest) -> List[str]:
        encoded = [
            self.tokenizer.apply_chat_template(
                c,
                # tools=[],
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            )
             for c in payload["conversations"]]
        ids = [e["input_ids"].squeeze(0) for e in encoded]
        masks = [e["attention_mask"].squeeze(0) for e in encoded]
        padded_ids = pad_sequence(ids, batch_first=True, padding_value=self.tokenizer.pad_token_id)
        padded_masks = pad_sequence(masks, batch_first=True, padding_value=0)
        padded_ids = padded_ids.to(self.model.device)
        padded_masks = padded_masks.to(self.model.device)

        top_p = payload.get("top_p", self.default_top_p)
        temperature = payload.get("temperature", self.default_temperature)
        max_tokens = payload.get("max_tokens") or self._compute_max_new_tokens(padded_ids.size(1))

        outputs = self._batch_generate(padded_ids, padded_masks, max_tokens, top_p, temperature)

        def _extract_response(text: str) -> str:
            bos_token_text = self.tokenizer.decode(self.tokenizer.bos_token_id, skip_special_tokens=False)
            eos_token_text = self.tokenizer.decode(self.tokenizer.eos_token_id, skip_special_tokens=False)
            pad_token_text = self.tokenizer.decode(self.tokenizer.pad_token_id, skip_special_tokens=False)
            
            text = text.strip()
            text = re.sub(re.escape(bos_token_text), "", text)
            text = re.sub(re.escape(eos_token_text), "", text)
            text = re.sub(re.escape(pad_token_text), "", text)
            response = text.split("[/INST]")[-1].strip()
            return response

        # I encountered a bug where if skip_special_tokens=True is used, it omitted the [INST] token.
        # so I simply implemented _extract_response manually.
        return [
            _extract_response(self.tokenizer.decode(o, skip_special_tokens=False)) for o in outputs
        ]

