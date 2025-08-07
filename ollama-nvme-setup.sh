#!/bin/bash
set -euo pipefail

# Ollama NVMe Configuration Script

NVME_OLLAMA="/mnt/nvme/ollama"

echo "=== Configuring Ollama for NVMe storage ==="

# Set environment variable
export OLLAMA_MODELS=${NVME_OLLAMA}

# Create Ollama systemd service override
echo "Creating Ollama systemd service override..."
sudo mkdir -p /etc/systemd/system/ollama.service.d

sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null << EOF
[Service]
Environment="OLLAMA_MODELS=${NVME_OLLAMA}"
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

echo "✓ Systemd override created"

# Reload systemd and restart Ollama if running
if systemctl is-active --quiet ollama; then
    echo "Restarting Ollama service..."
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    echo "✓ Ollama service restarted"
else
    sudo systemctl daemon-reload
    echo "✓ Systemd configuration reloaded (Ollama not running)"
fi

# Test Ollama configuration
echo ""
echo "Testing Ollama configuration..."
echo "OLLAMA_MODELS is set to: ${OLLAMA_MODELS}"
echo ""

# Example pull command
echo "To pull a model, use:"
echo "  ollama pull llama2:7b"
echo ""
echo "Models will be stored in: ${NVME_OLLAMA}"