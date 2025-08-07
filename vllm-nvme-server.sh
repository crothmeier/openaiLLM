#!/bin/bash
set -euo pipefail

# vLLM Server with NVMe Storage Configuration

# Source security validation module
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./security/validate.sh
source "${SCRIPT_DIR}/security/validate.sh"

MODEL="${1:-meta-llama/Llama-2-7b-hf}"
PORT="${2:-8000}"
GPU_MEM="${3:-0.90}"

# Validate model ID
if ! validate_hf_model_id "$MODEL"; then
    echo "Error: Invalid model ID" >&2
    exit 1
fi

# Validate port number
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
    echo "Error: Invalid port number (must be 1024-65535)" >&2
    exit 1
fi

# Validate GPU memory utilization
if ! [[ "$GPU_MEM" =~ ^0?\.[0-9]+$|^1\.0$ ]]; then
    echo "Error: Invalid GPU memory utilization (must be 0.0-1.0)" >&2
    exit 1
fi

# Ensure environment is configured
export HF_HOME=/mnt/nvme/hf-cache
export TRANSFORMERS_CACHE=/mnt/nvme/hf-cache
export HUGGINGFACE_HUB_CACHE=/mnt/nvme/hf-cache

# Validate environment variables
if ! validate_env_vars; then
    echo "Error: Environment validation failed" >&2
    exit 1
fi

# Validate download directory
DOWNLOAD_DIR="/mnt/nvme/models"
if ! validate_write_directory "$DOWNLOAD_DIR" >/dev/null; then
    echo "Error: Download directory validation failed" >&2
    exit 1
fi

echo "Starting vLLM server with NVMe storage..."
echo "Model: ${MODEL}"
echo "Port: ${PORT}"
echo "GPU Memory: ${GPU_MEM}"
echo "Download dir: ${DOWNLOAD_DIR}"
echo ""

log_security_event "VLLM_START" "Model: ${MODEL}, Port: ${PORT}"

# Run vLLM with explicit NVMe paths
vllm serve "${MODEL}" \
    --download-dir "${DOWNLOAD_DIR}" \
    --gpu-memory-utilization "${GPU_MEM}" \
    --port "${PORT}" \
    --host 0.0.0.0 \
    --tensor-parallel-size 1 \
    --dtype auto \
    --max-model-len 4096