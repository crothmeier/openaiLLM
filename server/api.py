#!/usr/bin/env python3
"""
Minimal FastAPI application for NVMe-backed model serving.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import os
import sys
import time
import asyncio
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from nvme_models.cache_manager import ModelCacheManager
    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False
    logger = logging.getLogger(__name__)
    logger.warning("Cache manager not available, caching features disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NVMe Model Server",
    description="FastAPI server for NVMe-backed model serving with intelligent caching",
    version="0.2.0"
)

# Initialize cache manager if available
cache_manager = None
if CACHE_ENABLED:
    nvme_path = os.environ.get("NVME_MOUNT_PATH", "/mnt/nvme")
    cache_manager = ModelCacheManager(
        nvme_path=nvme_path,
        max_cache_size_gb=int(os.environ.get("MAX_CACHE_SIZE_GB", "500")),
        target_free_space_percent=float(os.environ.get("TARGET_FREE_SPACE_PERCENT", "0.2"))
    )
    logger.info("Cache manager initialized")

# Health check response model
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str = "nvme-model-server"
    checks: Dict[str, Any] = {}

# Cache-related models
class ModelLoadRequest(BaseModel):
    model_id: str = Field(..., description="Model identifier")
    provider: str = Field("huggingface", description="Model provider (huggingface, ollama, vllm)")
    priority: str = Field("normal", description="Load priority (low, normal, high)")
    
class ModelLoadResponse(BaseModel):
    model_id: str
    status: str  # loading, cached, ready
    estimated_time_ms: float
    cache_hit: bool
    message: str

class CacheStatsResponse(BaseModel):
    cache_enabled: bool
    cache_size_gb: float
    max_cache_size_gb: float
    cache_utilization: float
    num_cached_models: int
    total_accesses: int
    target_free_space_percent: float
    most_recently_used: List[Dict[str, Any]]
    least_recently_used: List[Dict[str, Any]]
    usage_patterns: Dict[str, Any]

class CacheClearRequest(BaseModel):
    force: bool = Field(False, description="Force clear all entries, otherwise keep frequently used")

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
    endpoints = {
        "health": "/health",
        "healthz": "/healthz",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }
    
    if CACHE_ENABLED:
        endpoints.update({
            "cache": {
                "stats": "/api/v1/cache/stats",
                "clear": "/api/v1/cache/clear",
                "model_load": "/api/v1/models/{model_id}/load"
            }
        })
    
    return {
        "message": "NVMe Model Server",
        "version": "0.2.0",
        "features": {
            "cache_enabled": CACHE_ENABLED,
            "cost_tracking": False,  # Will be enabled in Feature #2
            "ab_testing": False      # Will be enabled in Feature #3
        },
        "endpoints": endpoints
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    metrics_lines = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
        'http_requests_total{method="GET",endpoint="/health"} 0',
        "",
        "# HELP nvme_model_server_up NVMe Model Server up status",
        "# TYPE nvme_model_server_up gauge",
        "nvme_model_server_up 1",
    ]
    
    # Add cache metrics if available
    if cache_manager:
        stats = cache_manager.get_cache_stats()
        metrics_lines.extend([
            "",
            "# HELP model_cache_size_gb Current cache size in GB",
            "# TYPE model_cache_size_gb gauge",
            f"model_cache_size_gb {stats['cache_size_gb']:.2f}",
            "",
            "# HELP model_cache_utilization Cache utilization percentage",
            "# TYPE model_cache_utilization gauge",
            f"model_cache_utilization {stats['cache_utilization']:.3f}",
            "",
            "# HELP model_cache_entries Number of cached models",
            "# TYPE model_cache_entries gauge",
            f"model_cache_entries {stats['num_cached_models']}",
            "",
            "# HELP model_cache_accesses_total Total cache accesses",
            "# TYPE model_cache_accesses_total counter",
            f"model_cache_accesses_total {stats['total_accesses']}",
        ])
    
    metrics_text = "\n".join(metrics_lines) + "\n"
    return JSONResponse(
        content=metrics_text,
        media_type="text/plain; version=0.0.4"
    )

# Cache API endpoints
@app.post("/api/v1/models/{model_id}/load", response_model=ModelLoadResponse)
async def load_model(model_id: str, request: ModelLoadRequest, background_tasks: BackgroundTasks):
    """Load a model into cache with intelligent pre-loading.
    
    This endpoint:
    - Checks if model is already cached (instant response)
    - Estimates load time based on model size
    - Triggers background loading if not cached
    - Updates usage patterns for predictive pre-loading
    """
    if not CACHE_ENABLED:
        raise HTTPException(status_code=503, detail="Cache manager not available")
    
    # Sanitize model_id
    model_id = model_id.replace("..", "").replace("/", "_")
    
    # Check if already cached
    if model_id in cache_manager._cache:
        # Record access and return immediately
        cache_manager.record_access(model_id, request.provider)
        return ModelLoadResponse(
            model_id=model_id,
            status="ready",
            estimated_time_ms=0,
            cache_hit=True,
            message="Model already cached and ready"
        )
    
    # Estimate load time
    estimated_time = cache_manager.get_model_load_time_estimate(model_id)
    
    # Trigger background loading
    async def load_model_background():
        try:
            # Simulate model loading (in real implementation, would call actual loader)
            await asyncio.sleep(estimated_time / 1000.0)
            
            # Record in cache
            cache_manager.record_access(
                model_id=model_id,
                provider=request.provider,
                size_gb=10.0,  # Would get actual size from loader
                load_time_ms=estimated_time,
                path=f"/mnt/nvme/models/{model_id}"
            )
            logger.info(f"Model {model_id} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
    
    background_tasks.add_task(load_model_background)
    
    return ModelLoadResponse(
        model_id=model_id,
        status="loading",
        estimated_time_ms=estimated_time,
        cache_hit=False,
        message=f"Model loading initiated, estimated time: {estimated_time/1000:.1f}s"
    )

@app.get("/api/v1/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get current cache statistics and usage patterns.
    
    Returns:
    - Cache size and utilization
    - Most/least recently used models
    - Usage patterns for predictive loading
    - Memory pressure indicators
    """
    if not CACHE_ENABLED:
        return CacheStatsResponse(
            cache_enabled=False,
            cache_size_gb=0,
            max_cache_size_gb=0,
            cache_utilization=0,
            num_cached_models=0,
            total_accesses=0,
            target_free_space_percent=0,
            most_recently_used=[],
            least_recently_used=[],
            usage_patterns={}
        )
    
    stats = cache_manager.get_cache_stats()
    return CacheStatsResponse(**stats, cache_enabled=True)

@app.post("/api/v1/cache/clear")
async def clear_cache(request: CacheClearRequest):
    """Clear the model cache.
    
    Args:
        force: If True, clear all entries. If False, keep frequently used models.
    
    Returns:
        Statistics about cleared models and freed space
    """
    if not CACHE_ENABLED:
        raise HTTPException(status_code=503, detail="Cache manager not available")
    
    result = cache_manager.clear_cache(force=request.force)
    return {
        "success": True,
        "cleared_models": result["cleared_models"],
        "cleared_size_gb": result["cleared_size_gb"],
        "kept_models": result.get("kept_models", 0),
        "force": result["force"],
        "message": f"Cleared {result['cleared_models']} models, freed {result['cleared_size_gb']:.1f}GB"
    }

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