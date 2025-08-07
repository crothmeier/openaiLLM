#!/bin/bash
# Backward compatibility wrapper for download-models.sh
# This script ensures the new Python CLI is used while maintaining the old interface

set -euo pipefail

# Check if nvme-models CLI is installed
if command -v nvme-models >/dev/null 2>&1; then
    # Parse the old menu-based interface and convert to CLI commands
    echo "=== Model Download Helper (using Python CLI) ==="
    echo ""
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
            nvme-models download "$model_id" --provider hf
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
            nvme-models download "$model_name" --provider ollama
            ;;
        
        3)
            nvme-models list
            ;;
        
        4)
            nvme-models verify
            ;;
        
        5)
            nvme-models clean
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
else
    echo "Python CLI not installed. Installing nvme-models package..."
    
    # Get the directory of this script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    # Install the package
    if [[ -f "$PROJECT_ROOT/setup.py" ]]; then
        pip install -e "$PROJECT_ROOT"
        
        # Re-run this script now that the CLI is installed
        exec "$0" "$@"
    else
        echo "Error: Could not find setup.py. Falling back to original script."
        # Fall back to original script if it exists
        if [[ -f "$SCRIPT_DIR/download-models.sh" ]]; then
            exec "$SCRIPT_DIR/download-models.sh" "$@"
        else
            echo "Error: Original download script not found."
            exit 1
        fi
    fi
fi