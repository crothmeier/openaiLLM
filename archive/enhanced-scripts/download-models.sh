#!/bin/bash
set -euo pipefail

# Model Download Script with Enhanced Reliability and Disk Space Checks

# Source utility functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/nvme_checks.sh"

# Source security validation module if it exists
if [[ -f "${SCRIPT_DIR}/../security/validate.sh" ]]; then
    source "${SCRIPT_DIR}/../security/validate.sh"
fi

# Ensure environment is set
export HF_HOME=/mnt/nvme/hf-cache
export TRANSFORMERS_CACHE=/mnt/nvme/hf-cache
export OLLAMA_MODELS=/mnt/nvme/ollama

echo "=== Model Download Helper with Reliability Safeguards ==="
echo "Storage locations:"
echo "  HF Cache: $HF_HOME"
echo "  Models: /mnt/nvme/models"
echo "  Ollama: $OLLAMA_MODELS"
echo ""

# Function to download HuggingFace models with enhanced checks
download_hf_model() {
    local model_id="$1"
    
    # Check NVMe is mounted
    check_nvme_mounted
    
    # Validate model ID using security module if available
    if command -v validate_hf_model_id >/dev/null 2>&1; then
        if ! validate_hf_model_id "$model_id"; then
            if command -v log_security_event >/dev/null 2>&1; then
                log_security_event "VALIDATION_FAILED" "Invalid HF model ID: $model_id"
            fi
            return 1
        fi
    fi
    
    # Validate environment variables if function exists
    if command -v validate_env_vars >/dev/null 2>&1; then
        validate_env_vars || return 1
    fi
    
    # Estimate model size
    echo "Estimating model size..."
    local estimated_size=$(estimate_model_size "$model_id")
    echo "  Estimated model size: ${estimated_size}GB"
    
    # Check disk space (require 2x model size for safety)
    local required_space=$((estimated_size * 2))
    echo "  Checking disk space (requiring ${required_space}GB for download and extraction)..."
    check_disk_space "$required_space"
    echo "  ✓ Sufficient disk space available"
    
    # Sanitize model name for filesystem
    local model_name
    if command -v sanitize_string >/dev/null 2>&1; then
        model_name=$(sanitize_string "$(echo "$model_id" | sed 's/\//-/g')")
    else
        model_name=$(echo "$model_id" | sed 's/\//-/g' | tr -d '[:punct:]' | tr ' ' '_')
    fi
    
    # Create temp directory for atomic download
    local temp_dir="/mnt/nvme/models/.tmp_${model_name}_$(date +%s)"
    local target_dir="/mnt/nvme/models/$model_name"
    
    # Validate target directory if function exists
    if command -v validate_write_directory >/dev/null 2>&1; then
        validate_write_directory "/mnt/nvme/models" >/dev/null || return 1
    fi
    
    echo "Downloading $model_id to temporary location..."
    if command -v log_security_event >/dev/null 2>&1; then
        log_security_event "DOWNLOAD_START" "HF model: $model_id"
    fi
    
    # Create temp directory
    mkdir -p "$temp_dir"
    
    # Download with resume support to temp directory
    if huggingface-cli download "$model_id" \
        --local-dir "$temp_dir" \
        --local-dir-use-symlinks False \
        --resume-download; then
        
        # Move to final location atomically
        echo "Moving model to final location..."
        if [[ -d "$target_dir" ]]; then
            echo "  Warning: Target directory exists. Backing up..."
            mv "$target_dir" "${target_dir}.backup.$(date +%s)"
        fi
        mv "$temp_dir" "$target_dir"
        
        echo "✓ Downloaded to $target_dir"
        echo "  Size: $(du -sh "$target_dir" | cut -f1)"
        
        if command -v log_security_event >/dev/null 2>&1; then
            log_security_event "DOWNLOAD_COMPLETE" "HF model: $model_id"
        fi
    else
        # Clean up temp directory on failure
        echo "Download failed. Cleaning up temporary files..."
        rm -rf "$temp_dir"
        return 1
    fi
}

# Function to pull Ollama models with disk space checks
pull_ollama_model() {
    local model="$1"
    
    # Check NVMe is mounted
    check_nvme_mounted
    
    # Validate Ollama model name using security module if available
    if command -v validate_ollama_model >/dev/null 2>&1; then
        if ! validate_ollama_model "$model"; then
            if command -v log_security_event >/dev/null 2>&1; then
                log_security_event "VALIDATION_FAILED" "Invalid Ollama model: $model"
            fi
            return 1
        fi
    fi
    
    # Validate environment variables if function exists
    if command -v validate_env_vars >/dev/null 2>&1; then
        validate_env_vars || return 1
    fi
    
    # Estimate size based on model name
    local estimated_size=15  # Default
    case "$model" in
        *:7b*|*7b*)
            estimated_size=8
            ;;
        *:13b*|*13b*)
            estimated_size=15
            ;;
        *:30b*|*30b*|*:33b*|*33b*)
            estimated_size=35
            ;;
        *:70b*|*70b*)
            estimated_size=70
            ;;
        *:8x7b*|*mixtral*)
            estimated_size=50
            ;;
    esac
    
    echo "  Estimated model size: ${estimated_size}GB"
    
    # Check disk space (require 2x model size for safety)
    local required_space=$((estimated_size * 2))
    echo "  Checking disk space (requiring ${required_space}GB)..."
    check_disk_space "$required_space"
    echo "  ✓ Sufficient disk space available"
    
    # Sanitize model name
    local sanitized_model
    if command -v sanitize_string >/dev/null 2>&1; then
        sanitized_model=$(sanitize_string "$model")
    else
        sanitized_model="$model"
    fi
    
    echo "Pulling Ollama model: $sanitized_model"
    if command -v log_security_event >/dev/null 2>&1; then
        log_security_event "DOWNLOAD_START" "Ollama model: $sanitized_model"
    fi
    
    if ollama pull "$sanitized_model"; then
        echo "✓ Model stored in $OLLAMA_MODELS"
        if command -v log_security_event >/dev/null 2>&1; then
            log_security_event "DOWNLOAD_COMPLETE" "Ollama model: $sanitized_model"
        fi
    else
        echo "Failed to pull Ollama model"
        return 1
    fi
}

# Function to clean up old temp directories
cleanup_temp_dirs() {
    echo "Cleaning up old temporary download directories..."
    find /mnt/nvme/models -maxdepth 1 -name ".tmp_*" -type d -mtime +1 -exec rm -rf {} \; 2>/dev/null || true
    echo "✓ Cleanup complete"
}

# Main menu
echo "Select operation:"
echo "1) Download HuggingFace model"
echo "2) Pull Ollama model"
echo "3) List downloaded models"
echo "4) Check storage usage"
echo "5) Clean up temporary files"
echo "6) Exit"
echo ""
read -p "Choice (1-6): " choice

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
            ls -la /mnt/nvme/models/ 2>/dev/null | grep -v "^total" | grep -v ".tmp_" || echo "  No models found"
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
        echo ""
        echo "Temporary files:"
        find /mnt/nvme/models -maxdepth 1 -name ".tmp_*" -type d -exec du -sh {} \; 2>/dev/null || echo "  No temporary files"
        ;;
    
    5)
        cleanup_temp_dirs
        ;;
    
    6)
        echo "Exiting..."
        exit 0
        ;;
    
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac