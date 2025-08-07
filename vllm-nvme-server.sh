#!/bin/bash
set -euo pipefail

# vLLM Server with NVMe Storage Configuration

MODEL="${1:-meta-llama/Llama-2-7b-hf}"
PORT="${2:-8000}"
GPU_MEM="${3:-0.90}"

# Ensure environment is configured
export HF_HOME=/mnt/nvme/hf-cache
export TRANSFORMERS_CACHE=/mnt/nvme/hf-cache
export HUGGINGFACE_HUB_CACHE=/mnt/nvme/hf-cache

echo "Starting vLLM server with NVMe storage..."
echo "Model: ${MODEL}"
echo "Port: ${PORT}"
echo "GPU Memory: ${GPU_MEM}"
echo "Download dir: /mnt/nvme/models"
echo ""

# Run vLLM with explicit NVMe paths
vllm serve ${MODEL} \
    --download-dir /mnt/nvme/models \
    --gpu-memory-utilization ${GPU_MEM} \
    --port ${PORT} \
    --host 0.0.0.0 \
    --tensor-parallel-size 1 \
    --dtype auto \
    --max-model-len 4096