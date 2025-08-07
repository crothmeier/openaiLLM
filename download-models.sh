#!/bin/bash
set -euo pipefail

# Model Download Script with NVMe Storage

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
    local model_id=$1
    local model_name=$(echo $model_id | sed 's/\//-/g')
    
    echo "Downloading $model_id to /mnt/nvme/models/$model_name..."
    
    huggingface-cli download "$model_id" \
        --local-dir "/mnt/nvme/models/$model_name" \
        --local-dir-use-symlinks False \
        --resume-download
    
    echo "✓ Downloaded to /mnt/nvme/models/$model_name"
    echo "  Size: $(du -sh /mnt/nvme/models/$model_name | cut -f1)"
}

# Function to pull Ollama models
pull_ollama_model() {
    local model=$1
    
    echo "Pulling Ollama model: $model"
    ollama pull "$model"
    
    echo "✓ Model stored in $OLLAMA_MODELS"
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