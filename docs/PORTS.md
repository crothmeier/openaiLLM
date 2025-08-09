# Port Allocation

This document defines the canonical port assignments for all services in the openaiLLM stack.

## Service Ports

| Service | Port | Binding | Status | Description |
|---------|------|---------|--------|-------------|
| **llama.cpp server** | 8010 | 127.0.0.1 | Active | Native llama.cpp inference server |
| **API (FastAPI)** | 8001 | 127.0.0.1 | Active | OpenAI-compatible API gateway |
| **Orchestrator** | 8002 | - | Reserved | Service orchestration layer |
| **JSON-Lite** | 8003 | - | Reserved | Lightweight JSON API |
| **Open WebUI** | 8080 | 0.0.0.0 | Active | Web interface for model interaction |

## Security Notes

- All services except Open WebUI bind to `127.0.0.1` (localhost-only) by default
- Open WebUI binds to `0.0.0.0` for container accessibility
- Port guard script (`check_port_free.sh`) enforces availability before service startup
- Systemd units include network sandboxing where appropriate

## Environment Variables

Services respect the following environment variables for port configuration:

```bash
LLAMA_PORT=8010        # llama.cpp server port
API_PORT=8001          # FastAPI gateway port
WEBUI_PORT=8080        # Open WebUI port
```

## Health Check Endpoints

Each active service provides health/metrics endpoints:

- **llama.cpp**: `http://127.0.0.1:8010/health`, `http://127.0.0.1:8010/metrics`
- **FastAPI**: `http://127.0.0.1:8001/health`
- **Open WebUI**: `http://127.0.0.1:8080/health`