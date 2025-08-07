# NVMe Model Storage Configuration

This repository contains scripts and configurations to ensure all AI model weights (Hugging Face, vLLM, Ollama) are stored on NVMe storage at `/mnt/nvme`.

## Quick Start

1. **Initial Setup** - Run this first:
```bash
chmod +x *.sh
sudo ./setup-nvme-models.sh
source ~/.bashrc
```

2. **Verify Configuration**:
```bash
./verify-nvme-storage.sh
```

3. **Download Models**:
```bash
./download-models.sh
```

## Components

### Core Scripts

- `setup-nvme-models.sh` - Main setup script that configures directories and environment variables
- `verify-nvme-storage.sh` - Verification script to check all configurations
- `download-models.sh` - Interactive model download helper

### vLLM Configuration

- `vllm-nvme-server.sh` - Launch vLLM server with NVMe storage
- `vllm-k8s-deployment.yaml` - Kubernetes deployment for vLLM

### Ollama Configuration  

- `ollama-nvme-setup.sh` - Configure Ollama for NVMe storage
- `docker-compose-ollama.yml` - Docker Compose setup for Ollama

### Systemd Services

- `systemd/vllm.service` - vLLM systemd service
- `systemd/install-services.sh` - Install systemd services

## Storage Paths

All models are stored under `/mnt/nvme`:

- **HuggingFace Cache**: `/mnt/nvme/hf-cache`
- **Model Downloads**: `/mnt/nvme/models`
- **Ollama Models**: `/mnt/nvme/ollama`

## Environment Variables

The following are set system-wide in `/etc/environment`:

```bash
HF_HOME=/mnt/nvme/hf-cache
TRANSFORMERS_CACHE=/mnt/nvme/hf-cache
HUGGINGFACE_HUB_CACHE=/mnt/nvme/hf-cache
OLLAMA_MODELS=/mnt/nvme/ollama
```

## Usage Examples

### Download HuggingFace Model
```bash
huggingface-cli download meta-llama/Llama-2-7b-hf \
  --local-dir /mnt/nvme/models/llama-2-7b-hf
```

### Start vLLM Server
```bash
./vllm-nvme-server.sh meta-llama/Llama-2-7b-hf 8000 0.90
```

### Pull Ollama Model
```bash
export OLLAMA_MODELS=/mnt/nvme/ollama
ollama pull llama2:7b
```

### Deploy with Docker Compose
```bash
docker-compose -f docker-compose-ollama.yml up -d
```

### Deploy on Kubernetes
```bash
kubectl create namespace ai-models
kubectl apply -f vllm-k8s-deployment.yaml
```

## Verification

Run the verification script to ensure everything is configured correctly:

```bash
./verify-nvme-storage.sh
```

This checks:
- NVMe mount point
- Directory structure
- Environment variables
- Symlinks
- Python/HF configuration
- Storage usage
- Model files

## Troubleshooting

### Environment Variables Not Set
```bash
source ~/.bashrc
# or for system-wide:
source /etc/environment
```

### Permission Issues
```bash
sudo chown -R $USER:$USER /mnt/nvme
```

### vLLM Legacy Cache
For vLLM versions ≤0.10.1:
```bash
mkdir -p ~/.cache/huggingface
ln -s /mnt/nvme/hf-cache ~/.cache/huggingface
```

### Check Service Status
```bash
sudo systemctl status vllm
sudo journalctl -u vllm -f
```

## Performance Optimization

### Filesystem Mount Options
Add to `/etc/fstab` for NVMe:
```
UUID=<nvme-uuid> /mnt/nvme ext4 defaults,noatime,discard 0 2
```

### GPU Memory Settings
Adjust in vLLM scripts:
- `--gpu-memory-utilization 0.90` (90% GPU memory)
- `--tensor-parallel-size 1` (single GPU)

## Security Notes

- Never commit API keys or tokens
- Set appropriate file permissions on model directories
- Use service accounts for production deployments
- Enable authentication for exposed endpoints