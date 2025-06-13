from dataclasses import dataclass
from typing import List, Literal, Optional, TypedDict, Union
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
from collections import defaultdict
from termcolor import colored
import traceback


MISTRAL_7B_INSTRUCT = "mistralai/Mistral-7B-Instruct-v0.1"

MAX_CONTEXT_TOKENS = 32768

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
    max_tokens: int
    temperature: Optional[float]


@dataclass
class OutOfTokensError(Exception):
    budget: int
    total_tokens: int


@dataclass
class OutOfMemoryError(Exception):
    device_or_devices: Union[str, List[str]]
    used: int
    requested: int


@dataclass
class UnfinishedResponseError(Exception):
    max_new_tokens: int
    generation: str


class Mistral:

    def __init__(
        self,
        model_id: str = MISTRAL_7B_INSTRUCT,
        max_context_tokens: int = MAX_CONTEXT_TOKENS,
        quantization: Optional[Literal["8bit", "4bit"]] = None,
        default_temperature: float = 0.6,
        default_top_p: float = 0.9,
    ):
        self.max_context_tokens = max_context_tokens
        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        if quantization is not None:
            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                device_map="auto",
                torch_dtype=torch.float16,
                quantization_config=(
                    bnb_config_4bit if quantization == "4bit" else bnb_config_8bit
                ),
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_id, device_map="auto", torch_dtype=torch.float16
            )
        self.model = model
        self.default_temperature = default_temperature
        self.default_top_p = default_top_p

    def completion(self, payload: CompletionRequest) -> str:
        messages = payload["messages"]
        top_p = payload.get("top_p", self.default_top_p)
        max_tokens = payload.get("max_tokens", None)
        if max_tokens is None:
            raise ValueError(
                "max_tokens is required. To simulate an unlimited response, consider supplying a very large value."
            )

        temperature = payload.get("temperature", self.default_temperature)

        formatted_text = self.tokenizer.apply_chat_template(messages, tokenize=False)
        inputs = self.tokenizer(formatted_text, return_tensors="pt")
        input_ids = inputs["input_ids"]
        total_input_tokens = input_ids.shape[1]

        if total_input_tokens > MAX_CONTEXT_TOKENS:
            raise OutOfTokensError(
                budget=MAX_CONTEXT_TOKENS, total_tokens=total_input_tokens
            )

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
                # Determine which devices the model is on:
                # Transformers v4.35+ stores its placement in hf_device_map
                device_map = getattr(self.model, "hf_device_map", None)
                # Fallback: if it's just on one device (legacy), wrap it into a dict
                if device_map is None:
                    # model.device might be a torch.device, or accelerator.device…
                    device_map = {"": self.model.device}

                used_per_device = {}
                requested_per_device = {}
                for name, dev in device_map.items():
                    if dev.type == "cuda":
                        idx = dev.index if dev.index is not None else 0
                        used = torch.cuda.memory_allocated(idx)
                        # Approximate “requested” as whatever new allocation we tried;
                        # you might refine this calculation based on your actual tensors
                        requested = (
                            max_tokens
                            * inputs["input_ids"].element_size()
                            * inputs["input_ids"].nelement()
                        )
                        used_per_device[f"cuda:{idx}"] = used
                        requested_per_device[f"cuda:{idx}"] = requested
                        # Clear cache per device
                        torch.cuda.empty_cache(idx)
                    else:
                        used_per_device[str(dev)] = 0
                        requested_per_device[str(dev)] = 0

                raise OutOfMemoryError(
                    device_or_devices=list(used_per_device.keys()),
                    used=used_per_device,
                    requested=requested_per_device,
                )
            raise

        # Check unfinished response
        gen_len = output.shape[1] - input_ids.shape[1]
        if gen_len >= max_tokens:
            generated_ids = output[0][input_ids.shape[1] :]
            debug_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False)
            raise UnfinishedResponseError(
                max_new_tokens=max_tokens, generation=debug_text
            )

        decoded = self.tokenizer.decode(output[0], skip_special_tokens=True)
        reply = decoded.split("[/INST]")[-1].strip()
        return reply
