#!/bin/bash
set -euo pipefail

# Install systemd services for AI model servers

echo "=== Installing systemd services ==="

# Copy vLLM service
if [ -f "vllm.service" ]; then
    echo "Installing vLLM service..."
    sudo cp vllm.service /etc/systemd/system/
    sudo systemctl daemon-reload
    echo "✓ vLLM service installed"
    echo "  To enable: sudo systemctl enable vllm"
    echo "  To start: sudo systemctl start vllm"
    echo ""
fi

# Create environment persistence service
echo "Creating environment persistence service..."
sudo tee /etc/systemd/system/ai-nvme-env.service > /dev/null << 'EOF'
[Unit]
Description=Set AI Model NVMe Environment Variables
DefaultDependencies=no
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'echo "HF_HOME=/mnt/nvme/hf-cache" >> /etc/environment; echo "TRANSFORMERS_CACHE=/mnt/nvme/hf-cache" >> /etc/environment; echo "OLLAMA_MODELS=/mnt/nvme/ollama" >> /etc/environment'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ai-nvme-env.service
echo "✓ Environment persistence service installed and enabled"
echo ""

# Create mount verification service
echo "Creating NVMe mount verification service..."
sudo tee /etc/systemd/system/verify-nvme-models.service > /dev/null << 'EOF'
[Unit]
Description=Verify NVMe Model Storage Mount
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'if ! mountpoint -q /mnt/nvme; then echo "ERROR: /mnt/nvme not mounted!" && exit 1; fi'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable verify-nvme-models.service
echo "✓ Mount verification service installed and enabled"
echo ""

echo "=== Service installation complete ==="
echo ""
echo "Available services:"
echo "  - vllm.service: vLLM inference server"
echo "  - ai-nvme-env.service: Environment variable persistence (enabled)"
echo "  - verify-nvme-models.service: NVMe mount verification (enabled)"
echo ""
echo "Service management commands:"
echo "  sudo systemctl status <service-name>"
echo "  sudo systemctl start <service-name>"
echo "  sudo systemctl stop <service-name>"
echo "  sudo systemctl enable <service-name>"
echo "  sudo journalctl -u <service-name> -f"