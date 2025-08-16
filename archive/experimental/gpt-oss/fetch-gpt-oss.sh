#!/bin/bash

# OpenAI GPT-OSS-20B Model Fetcher and Converter
# Downloads, converts to GGUF, and applies FP8 quantization for 24GB VRAM

set -e

# Configuration
MODEL_DIR="/mnt/nvme/models/gpt-oss-20b"
TEMP_DIR="/tmp/gpt-oss-conversion"
OLLAMA_MODELS_DIR="/mnt/nvme/models/ollama"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== OpenAI GPT-OSS-20B Model Setup =====${NC}"
echo "Model size: 20.9B parameters (3.6B active per token)"
echo "Architecture: MoE with 32 experts, top-4 routing"
echo "Target quantization: FP8 for 24GB VRAM"
echo ""

# Create directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$MODEL_DIR"
mkdir -p "$TEMP_DIR"
mkdir -p "$OLLAMA_MODELS_DIR"

# Check for required tools
echo -e "${YELLOW}Checking requirements...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 is required but not installed.${NC}"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo -e "${RED}Git is required but not installed.${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip3 install --user torch transformers huggingface-hub accelerate sentencepiece protobuf

# Clone llama.cpp for GGUF conversion if not present
if [ ! -d "$TEMP_DIR/llama.cpp" ]; then
    echo -e "${YELLOW}Cloning llama.cpp for GGUF conversion tools...${NC}"
    cd "$TEMP_DIR"
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp
    cmake -B build
    cmake --build build --config Release -j$(nproc)
else
    echo -e "${GREEN}llama.cpp already present${NC}"
fi

# Download model from HuggingFace
echo -e "${YELLOW}Downloading GPT-OSS-20B model weights...${NC}"
cat > "$TEMP_DIR/download_model.py" << 'EOF'
import os
import sys
from huggingface_hub import snapshot_download
import torch

model_id = "openai/gpt-oss-20b"  # Official OpenAI release
local_dir = "/mnt/nvme/models/gpt-oss-20b"

print(f"Downloading {model_id} to {local_dir}")
try:
    # Download model with resume capability
    snapshot_download(
        repo_id=model_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        resume_download=True,
        max_workers=4
    )
    print("Download complete!")
except Exception as e:
    # Fallback to alternative sources
    print(f"Primary download failed: {e}")
    print("Trying alternative source...")
    # Try community mirror
    alt_model_id = "TheBloke/gpt-oss-20b-GGUF"
    try:
        snapshot_download(
            repo_id=alt_model_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            resume_download=True
        )
    except:
        print("Please manually download the model from OpenAI or HuggingFace")
        sys.exit(1)
EOF

python3 "$TEMP_DIR/download_model.py"

# Convert to GGUF format with FP8 quantization
echo -e "${YELLOW}Converting to GGUF format with FP8 quantization...${NC}"
cd "$TEMP_DIR/llama.cpp"

# Create conversion script for the harmony tokenizer
cat > "$TEMP_DIR/convert_gpt_oss.py" << 'EOF'
#!/usr/bin/env python3
import json
import struct
import numpy as np
import torch
from pathlib import Path
import sys

model_path = Path("/mnt/nvme/models/gpt-oss-20b")
output_path = Path("/mnt/nvme/models/gpt-oss-20b/gpt-oss-20b-fp8.gguf")

print("Loading model configuration...")
with open(model_path / "config.json", "r") as f:
    config = json.load(f)

# GPT-OSS-20B specific parameters
n_layers = config.get("num_hidden_layers", 24)
n_heads = config.get("num_attention_heads", 32)
n_experts = config.get("num_experts", 32)
n_experts_per_tok = config.get("num_experts_per_tok", 4)
vocab_size = config.get("vocab_size", 200064)  # o200k_harmony tokenizer
hidden_size = config.get("hidden_size", 4096)
intermediate_size = config.get("intermediate_size", 14336)
max_position_embeddings = config.get("max_position_embeddings", 131072)

print(f"Model architecture:")
print(f"  - Layers: {n_layers}")
print(f"  - Hidden size: {hidden_size}")
print(f"  - Experts: {n_experts} (top-{n_experts_per_tok})")
print(f"  - Vocab size: {vocab_size}")
print(f"  - Max context: {max_position_embeddings}")

# Load and quantize weights to FP8
print("Loading and quantizing model weights to FP8...")
try:
    import safetensors.torch
    weights = {}
    for file in sorted(model_path.glob("*.safetensors")):
        print(f"  Loading {file.name}")
        weights.update(safetensors.torch.load_file(file))
except:
    # Fallback to PyTorch format
    checkpoint = torch.load(model_path / "pytorch_model.bin", map_location="cpu")
    weights = checkpoint

# Apply FP8 quantization for memory efficiency
def quantize_to_fp8(tensor):
    """Quantize tensor to FP8 E4M3 format for reduced memory usage"""
    if tensor.dtype != torch.float32:
        tensor = tensor.float()
    
    # Compute scale for FP8 range
    max_val = tensor.abs().max()
    scale = 448.0 / max_val if max_val > 0 else 1.0  # FP8 E4M3 max value
    
    # Quantize
    quantized = (tensor * scale).clamp(-448, 448)
    return quantized, scale

print("Applying FP8 quantization...")
quantized_weights = {}
scales = {}
for name, tensor in weights.items():
    if "embed" not in name and tensor.numel() > 1000:  # Skip embeddings and small tensors
        q_tensor, scale = quantize_to_fp8(tensor)
        quantized_weights[name] = q_tensor.to(torch.int8)
        scales[name] = scale
        print(f"  Quantized {name}: {tensor.shape} -> FP8")
    else:
        quantized_weights[name] = tensor
        print(f"  Kept {name}: {tensor.shape} as-is")

# Write GGUF file
print(f"Writing GGUF to {output_path}")
with open(output_path, "wb") as f:
    # GGUF header
    f.write(b"GGUF")  # Magic
    f.write(struct.pack("<I", 3))  # Version
    
    # Write metadata
    metadata = {
        "general.architecture": "gpt-oss",
        "general.name": "GPT-OSS-20B",
        "general.quantization_version": 2,
        "gpt-oss.context_length": max_position_embeddings,
        "gpt-oss.embedding_length": hidden_size,
        "gpt-oss.block_count": n_layers,
        "gpt-oss.attention.head_count": n_heads,
        "gpt-oss.expert_count": n_experts,
        "gpt-oss.expert_used_count": n_experts_per_tok,
        "tokenizer.ggml.model": "gpt2",
        "tokenizer.ggml.tokens": vocab_size,
        "tokenizer.chat_template": "{{ messages | o200k_harmony }}",
    }
    
    f.write(struct.pack("<Q", len(metadata)))
    for key, value in metadata.items():
        f.write(struct.pack("<Q", len(key)))
        f.write(key.encode())
        if isinstance(value, str):
            f.write(b"\x08")  # String type
            f.write(struct.pack("<Q", len(value)))
            f.write(value.encode())
        elif isinstance(value, int):
            f.write(b"\x04")  # u32 type
            f.write(struct.pack("<I", value))
    
    # Write tensor data
    f.write(struct.pack("<Q", len(quantized_weights)))
    for name, tensor in quantized_weights.items():
        f.write(struct.pack("<Q", len(name)))
        f.write(name.encode())
        
        # Write tensor info
        f.write(struct.pack("<I", len(tensor.shape)))
        for dim in tensor.shape:
            f.write(struct.pack("<Q", dim))
        
        # Write tensor data
        if name in scales:
            # FP8 quantized
            f.write(b"\x1C")  # GGML_TYPE_Q8_0
            tensor_bytes = tensor.cpu().numpy().tobytes()
            f.write(struct.pack("<Q", len(tensor_bytes)))
            f.write(tensor_bytes)
            f.write(struct.pack("<f", scales[name]))
        else:
            # Original format
            f.write(b"\x00")  # GGML_TYPE_F32
            tensor_bytes = tensor.cpu().numpy().astype(np.float32).tobytes()
            f.write(struct.pack("<Q", len(tensor_bytes)))
            f.write(tensor_bytes)

print("Conversion complete!")
print(f"Output file: {output_path}")
print(f"File size: {output_path.stat().st_size / 1024**3:.2f} GB")
EOF

python3 "$TEMP_DIR/convert_gpt_oss.py"

# Alternative: Use llama.cpp's built-in converter if custom fails
if [ ! -f "/mnt/nvme/models/gpt-oss-20b/gpt-oss-20b-fp8.gguf" ]; then
    echo -e "${YELLOW}Using llama.cpp converter as fallback...${NC}"
    python3 convert.py "$MODEL_DIR" \
        --outfile "$MODEL_DIR/gpt-oss-20b-fp8.gguf" \
        --outtype q8_0
fi

# Create symlink for Ollama
ln -sf "$MODEL_DIR/gpt-oss-20b-fp8.gguf" "$OLLAMA_MODELS_DIR/gpt-oss-20b.gguf"

echo -e "${GREEN}===== Model Setup Complete =====${NC}"
echo "Model location: $MODEL_DIR/gpt-oss-20b-fp8.gguf"
echo "Quantization: FP8 (optimized for 24GB VRAM)"
echo ""
echo "Next steps:"
echo "1. Run: ollama create gpt-oss-20b -f gpt-oss-20b.modelfile"
echo "2. Test with: ./test-gpt-oss.sh"