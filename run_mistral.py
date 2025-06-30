from dataclasses import dataclass
from typing import List, Literal, Optional, TypedDict, Union
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
from collections import defaultdict
from termcolor import colored
import traceback


MISTRAL_7B_INSTRUCT = "mistralai/Mistral-7B-Instruct-v0.1"

bnb_config_8bit = BitsAndBytesConfig(
    load_in_4bit=False,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
)

bnb_config_4bit = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
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
        model_id: str = MISTRAL_7B_INSTRUCT,
        quantization: Optional[Literal["8bit", "4bit"]]=None,
        default_temperature: float = 0.6,
        default_top_p: float = 0.9,
        pad_margin: int = 2,
    ):
        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        if quantization is not None:
            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                device_map="auto",
                torch_dtype=torch.float16,
                quantization_config=(bnb_config_4bit if quantization=="4bit" else bnb_config_8bit),
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_id, device_map="auto", torch_dtype=torch.float16
            )
        self.model = model
        self.default_temperature = default_temperature
        self.default_top_p = default_top_p
        self.pad_margin = pad_margin
        # load config limits
        cfg = self.model.config
        self.hard_limit = getattr(cfg, "max_position_embeddings", None)
        self.sliding_window = getattr(cfg, "sliding_window", None)

    def _compute_max_new_tokens(self, input_ids_len: int) -> int:
        # Prefer sliding window heuristic if available
        budget = self.sliding_window or self.hard_limit
        if budget is None:
            raise ValueError("Model configuration missing context limits.")
        return max(0, budget - input_ids_len - self.pad_margin)

    def completion(self, payload: CompletionRequest) -> str:
        messages = payload["messages"]
        top_p = payload.get("top_p", self.default_top_p)
        max_tokens = payload.get("max_tokens", None)

        temperature = payload.get("temperature", self.default_temperature)

        formatted_text = self.tokenizer.apply_chat_template(messages, tokenize=False)
        inputs = self.tokenizer(formatted_text, return_tensors="pt")
        input_ids = inputs["input_ids"]
        total_input_tokens = input_ids.shape[1]

        # Check against hard limit
        if self.hard_limit and total_input_tokens > self.hard_limit:
            raise OutOfTokensError(budget=self.hard_limit, total_tokens=total_input_tokens)

        # Compute max_new_tokens if not provided
        if max_tokens is None:
            max_tokens = self._compute_max_new_tokens(total_input_tokens)

        try:
            output = self.model.generate(
                input_ids.to(self.model.device),
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                attention_mask=inputs["attention_mask"].to(self.model.device),
            )

        except RuntimeError as e:
            traceback.print_exc()
            if "out of memory" in str(e):
                # gather memory stats
                device_map = getattr(self.model, "hf_device_map", None) or {"": self.model.device}
                used_per_device, requested_per_device = {}, {}
                for name, dev in device_map.items():
                    if dev.type=="cuda":
                        idx = dev.index or 0
                        used = torch.cuda.memory_allocated(idx)
                        requested = max_tokens * input_ids.element_size() * input_ids.nelement()
                        used_per_device[f"cuda:{idx}"]=used
                        requested_per_device[f"cuda:{idx}"]=requested
                        torch.cuda.empty_cache(idx)
                    else:
                        used_per_device[str(dev)] = 0
                        requested_per_device[str(dev)] = 0
                raise OutOfMemoryError(device_or_devices=list(used_per_device.keys()), used=used_per_device, requested=requested_per_device)
            raise

        gen_len = output.shape[1] - total_input_tokens
        if gen_len >= max_tokens:
            generated_ids = output[0][total_input_tokens:]
            debug_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False)
            raise UnfinishedResponseError(max_new_tokens=max_tokens, generation=debug_text)

        decoded = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return decoded.split("[/INST]")[-1].strip()
