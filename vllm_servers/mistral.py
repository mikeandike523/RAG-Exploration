from vllm import LLM

import click

@click.command()
@click.option('--model', default='mistralai/Mistral-Nemo-Instruct-2407', help='The Hugging Face model to use.')
def main(model):

    llm = LLM(
        # Model & tokenizer
        model=model,   # HF model to load
        tokenizer=None,                                 # default → same as `model`
        tokenizer_mode="mistral",                       # use mistral_common tokenizer
        skip_tokenizer_init=False,                      # load tokenizer at init
        trust_remote_code=False,                        # do not run hub code

        # Data types & quantization
        dtype="bfloat16",                               # weights & activations dtype :contentReference[oaicite:0]{index=0}
        quantization="fp8",                             # experimental 8-bit weight quant :contentReference[oaicite:1]{index=1}
        # (if you wanted bitsandbytes: quantization="bitsandbytes")

        # Parallelism
        tensor_parallel_size=2,                         # split weights 2-way across GPUs :contentReference[oaicite:2]{index=2}
        pipeline_parallel_size=1,                       # no pipeline split :contentReference[oaicite:3]{index=3}
        distributed_executor_backend="mp",               # use multiprocessing (default for >1 GPU) :contentReference[oaicite:4]{index=4}

        # GPU memory budgeting
        gpu_memory_utilization=0.9,                     # use 100% of GPU for weights/KV/acts before offload :contentReference[oaicite:5]{index=5}
        swap_space=16,                                  # up to 16 GiB per GPU for KV swap to CPU :contentReference[oaicite:6]{index=6}

        # CPU offload
        cpu_offload_gb=96,                              # up to 96 GiB for weight overflow → RAM :contentReference[oaicite:7]{index=7}

        # Context & compile thresholds
        max_model_len=8192,                             # cap model context at 8 K tokens (EngineArg)
        max_seq_len_to_capture=8192,                    # CUDA-graph compile up to 8 K tokens :contentReference[oaicite:8]{index=8}

        # CUDA-graph / execution control
        enforce_eager=False,                            # use CUDA graph + eager hybrid :contentReference[oaicite:9]{index=9}
        block_size=16,                                  # token block size for prefill & chunking :contentReference[oaicite:10]{index=10}

        # Reduction & async output
        disable_custom_all_reduce=False,                 # allow optimized all-reduce
        disable_async_output_proc=False,                 # keep async output processing

        # Prefix caching / sliding window
        enable_prefix_caching=False,
        disable_sliding_window=False,

        # Multimodal / plugin hooks
        mm_processor_kwargs=None,

        # Device target
        device="cuda",                                  # run on CUDA GPUs :contentReference[oaicite:11]{index=11}
    )

    for rank, worker in enumerate(llm.engine_core.workers):
        print(f"\n=== Worker {rank} ===")
        worker.model_runner.report_model_shard_distribution()
        worker.model_runner.report_memory_usage()

if __name__ == "__main__":
    main()