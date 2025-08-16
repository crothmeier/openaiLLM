#!/usr/bin/env python3
"""
Minimal FastAPI application for NVMe-backed model serving.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NVMe Model Server",
    description="FastAPI server for NVMe-backed model serving",
    version="0.1.0"
)

# Health check response model
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str = "nvme-model-server"
    checks: Dict[str, Any] = {}

@app.get("/health", response_model=HealthResponse)
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for readiness/liveness probes."""
    checks = {}
    
    # Check NVMe mount
    nvme_path = os.environ.get("NVME_MOUNT_PATH", "/mnt/nvme")
    if os.path.exists(nvme_path) and os.path.ismount(nvme_path):
        checks["nvme_mount"] = "ok"
    else:
        checks["nvme_mount"] = "not_mounted"
    
    # Check if models directory exists
    models_dir = os.path.join(nvme_path, "models")
    if os.path.exists(models_dir):
        checks["models_directory"] = "ok"
    else:
        checks["models_directory"] = "not_found"
    
    return HealthResponse(
        status="healthy" if all(v == "ok" for v in checks.values()) else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        checks=checks
    )

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "NVMe Model Server",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "healthz": "/healthz",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (placeholder)."""
    # Basic Prometheus format metrics
    metrics_text = """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health"} 0

# HELP nvme_model_server_up NVMe Model Server up status
# TYPE nvme_model_server_up gauge
nvme_model_server_up 1
"""
    return JSONResponse(
        content=metrics_text,
        media_type="text/plain; version=0.0.4"
    )

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "path": str(request.url.path)}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")