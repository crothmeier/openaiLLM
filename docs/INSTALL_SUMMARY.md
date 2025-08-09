# llama.cpp Service Installation Summary

## Current Status
- **Port 8080**: Occupied by Open WebUI (PID 4578)
- **Port 8010**: Available (chosen for llama.cpp)
- **Binary**: Ready at `build/bin/llama-server`
- **Model**: ⚠️ **MISSING** - Expected at `/mnt/nvme/models/gpt-oss-20b/gpt-oss-20b.Q8_0.gguf`

## Files Prepared
1. `llamacpp.service` - Hardened systemd unit file
2. `llamacpp-env.conf` - Environment configuration
3. `install_service.sh` - Installation script

## Installation Commands
Run these commands with sudo to complete the installation:

```bash
# 1. Run the installation script
sudo ./install_service.sh

# OR manually execute these commands:
sudo id llama >/dev/null 2>&1 || sudo useradd --system --home /srv/llama --shell /usr/sbin/nologin llama
sudo mkdir -p /srv/llama /var/log/openaiLLM
sudo install -m 0755 -D build/bin/llama-server /srv/llama/llama-server
sudo chown -R llama:llama /srv/llama /var/log/openaiLLM
sudo cp llamacpp-env.conf /etc/default/llamacpp
sudo cp llamacpp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable llamacpp.service
```

## IMPORTANT: Model Required
The service **WILL NOT START** without a valid model file. You need to:

1. Download or place the model at: `/mnt/nvme/models/gpt-oss-20b/gpt-oss-20b.Q8_0.gguf`
2. Update `/etc/default/llamacpp` with the correct `MODEL_PATH`
3. Start the service: `sudo systemctl start llamacpp.service`

## Service Configuration
- **Port**: 8010 (standardized)
- **Host**: 127.0.0.1 (localhost only)
- **User**: llama (system user)
- **Config**: `/etc/default/llamacpp`
- **Binary**: `/srv/llama/llama-server`
- **Logs**: `/var/log/openaiLLM/` and `journalctl -u llamacpp.service`

## Security Features
- Runs as unprivileged system user
- Sandboxed with systemd hardening (ProtectSystem=strict, ProtectHome=yes)
- Read-only filesystem except for specific paths
- Memory locking enabled for performance
- Network access restricted to localhost

## Verification Commands
```bash
# Check service status
sudo systemctl status llamacpp.service

# Check logs
sudo journalctl -u llamacpp.service -f

# Check port listener
ss -ltn '( sport = :8010 )'

# Test endpoint (once running)
curl http://127.0.0.1:8010/health
```

## Port Standardization
- **8080**: Open WebUI (existing)
- **8010**: llama.cpp (NEW)
- **8001**: FastAPI (if needed)