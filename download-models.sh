#!/bin/bash
set -euo pipefail

# Model Download Script with NVMe Storage

# Source security validation module
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./security/validate.sh
source "${SCRIPT_DIR}/security/validate.sh"

# Ensure environment is set
export HF_HOME=/mnt/nvme/hf-cache
export TRANSFORMERS_CACHE=/mnt/nvme/hf-cache
export OLLAMA_MODELS=/mnt/nvme/ollama

echo "=== Model Download Helper ==="
echo "Storage locations:"
echo "  HF Cache: $HF_HOME"
echo "  Models: /mnt/nvme/models"
echo "  Ollama: $OLLAMA_MODELS"
echo ""

# Function to download HuggingFace models
download_hf_model() {
    local model_id="$1"
    
    # First validate with the new validate_model_id function for path traversal
    if ! validate_model_id "$model_id"; then
        log_security_event "VALIDATION_FAILED" "Model ID validation failed: $model_id"
        exit 1  # Exit nonzero on violation
    fi
    
    # Then validate HF-specific format
    if ! validate_hf_model_id "$model_id"; then
        log_security_event "VALIDATION_FAILED" "Invalid HF model ID format: $model_id"
        exit 1  # Exit nonzero on violation
    fi
    
    # Validate environment variables
    validate_env_vars || return 1
    
    # Sanitize model name for filesystem
    local model_name
    model_name=$(sanitize_string "$(echo "$model_id" | sed 's/\//-/g')")
    
    # Validate target directory
    local target_dir="/mnt/nvme/models/$model_name"
    validate_write_directory "/mnt/nvme/models" >/dev/null || return 1
    
    echo "Downloading $model_id to $target_dir..."
    log_security_event "DOWNLOAD_START" "HF model: $model_id"
    
    # Add --no-symlinks flag for security
    huggingface-cli download "$model_id" \
        --local-dir "$target_dir" \
        --local-dir-use-symlinks False \
        --no-symlinks \
        --resume-download
    
    echo "✓ Downloaded to $target_dir"
    echo "  Size: $(du -sh "$target_dir" | cut -f1)"
    log_security_event "DOWNLOAD_COMPLETE" "HF model: $model_id"
}

# Function to pull Ollama models
pull_ollama_model() {
    local model="$1"
    
    # First validate with the new validate_model_id function for path traversal
    if ! validate_model_id "$model"; then
        log_security_event "VALIDATION_FAILED" "Model ID validation failed: $model"
        exit 1  # Exit nonzero on violation
    fi
    
    # Then validate Ollama-specific format
    if ! validate_ollama_model "$model"; then
        log_security_event "VALIDATION_FAILED" "Invalid Ollama model format: $model"
        exit 1  # Exit nonzero on violation
    fi
    
    # Validate environment variables
    validate_env_vars || return 1
    
    # Sanitize model name
    local sanitized_model
    sanitized_model=$(sanitize_string "$model")
    
    echo "Pulling Ollama model: $sanitized_model"
    log_security_event "DOWNLOAD_START" "Ollama model: $sanitized_model"
    
    ollama pull "$sanitized_model"
    
    echo "✓ Model stored in $OLLAMA_MODELS"
    log_security_event "DOWNLOAD_COMPLETE" "Ollama model: $sanitized_model"
}

# Main menu
echo "Select operation:"
echo "1) Download HuggingFace model"
echo "2) Pull Ollama model"
echo "3) List downloaded models"
echo "4) Check storage usage"
echo "5) Exit"
echo ""
read -p "Choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "Popular models:"
        echo "  - meta-llama/Llama-2-7b-hf"
        echo "  - mistralai/Mistral-7B-v0.1"
        echo "  - google/flan-t5-xl"
        echo "  - facebook/opt-6.7b"
        echo ""
        read -p "Enter HuggingFace model ID: " model_id
        download_hf_model "$model_id"
        ;;
    
    2)
        echo ""
        echo "Popular Ollama models:"
        echo "  - llama2:7b"
        echo "  - mistral:7b"
        echo "  - codellama:13b"
        echo "  - mixtral:8x7b"
        echo ""
        read -p "Enter Ollama model name: " model_name
        pull_ollama_model "$model_name"
        ;;
    
    3)
        echo ""
        echo "=== Downloaded Models ==="
        echo ""
        echo "HuggingFace models in /mnt/nvme/models:"
        if [ -d /mnt/nvme/models ]; then
            ls -la /mnt/nvme/models/ 2>/dev/null || echo "  No models found"
        else
            echo "  Directory not found"
        fi
        echo ""
        echo "Ollama models:"
        ollama list 2>/dev/null || echo "  Ollama not running or no models"
        ;;
    
    4)
        echo ""
        echo "=== Storage Usage ==="
        df -h /mnt/nvme
        echo ""
        echo "Directory sizes:"
        du -sh /mnt/nvme/* 2>/dev/null | sort -rh
        ;;
    
    5)
        echo "Exiting..."
        exit 0
        ;;
    
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac