#!/bin/bash

# Direct test of GPT-OSS-20B with llama.cpp

echo "Testing GPT-OSS-20B directly with llama.cpp..."
echo "Model: gpt-oss-20b-fp8.gguf"
echo ""

# Test with a simple prompt
./llama.cpp/build/bin/llama-cli \
    -m /mnt/nvme/models/gpt-oss-20b/gpt-oss-20b-fp8.gguf \
    -p "Write a haiku about Phoenix in summer." \
    -n 128 \
    --temp 0.7 \
    --top-p 0.95 \
    --ctx-size 4096 \
    2>&1

echo ""
echo "Test complete!"