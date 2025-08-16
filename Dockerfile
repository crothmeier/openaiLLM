# Simple single-stage Dockerfile for faster builds
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NVME_MODELS_ENV_FILE=/etc/nvme-models/runtime.env \
    LOG_LEVEL=INFO

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir uvicorn fastapi structlog

# Copy application code
COPY nvme_models/ nvme_models/
COPY server/ server/
COPY setup.py .
RUN pip install -e .

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /app app && \
    mkdir -p /etc/nvme-models && chown -R app:app /etc/nvme-models /app

USER app:app
EXPOSE 8001

CMD ["uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]