# syntax=docker/dockerfile:1.7
# --- Builder ---
FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# System deps if needed (curl for health debug)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt* pyproject.toml* setup.cfg* setup.py* ./
# If you don't have pinned reqs, fallback to minimal runtime deps
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
RUN pip install uvicorn fastapi structlog
COPY . .
RUN pip install -e . || true

# --- Runtime (non-root) ---
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    NVME_MODELS_ENV_FILE=/etc/nvme-models/runtime.env \
    LOG_LEVEL=INFO
WORKDIR /app
# Create unprivileged user
RUN groupadd -r app && useradd -r -g app -d /app app
# Minimal OS deps and cleanup
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
# Runtime env file location (K8s will mount/override)
RUN mkdir -p /etc/nvme-models && chown -R app:app /etc/nvme-models
USER app:app
EXPOSE 8001
# Health/readiness are on /health; JSON logs by app
CMD ["uvicorn","server.api:app","--host","0.0.0.0","--port","8001","--log-level","info"]