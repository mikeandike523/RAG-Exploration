#!/bin/bash

export NVIDIA_VISIBLE_DEVICES="1,2"
export CUDA_VISIBLE_DEVICES="1,2"

vllm serve mistralai/Mistral-Nemo-Instruct-2407 \
  --tokenizer-mode mistral \
  --dtype bfloat16 \
  --quantization fp8 \
  --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 \
  --gpu-memory-utilization 0.85 \
  --swap-space 16 \
  --cpu-offload-gb 96 \
  --max-model-len 8192 \
  --max-seq-len-to-capture 8192 \
  --port 8008
