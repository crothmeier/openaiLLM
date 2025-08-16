"""Structured logging configuration using structlog."""

import os
import structlog
import logging
from pathlib import Path
from typing import Any, Dict

def sanitize_path(path: Any) -> str:
    """Sanitize paths for logging to avoid leaking absolute paths."""
    if path is None:
        return "none"
    
    path_str = str(path)
    home = str(Path.home())
    
    # Replace home directory with ~
    if home in path_str:
        path_str = path_str.replace(home, "~")
    
    # For /mnt/nvme paths, show relative to base
    if "/mnt/nvme" in path_str:
        path_str = path_str.replace("/mnt/nvme/", "nvme://")
    
    return path_str

def setup_logging(log_level: str = "INFO"):
    """Configure structured JSON logging with structlog."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

# Context managers for adding context
def with_model_context(logger: structlog.BoundLogger, model_id: str, provider: str):
    """Add model context to logger."""
    return logger.bind(model_id=model_id, provider=provider)

def with_action_context(logger: structlog.BoundLogger, action: str):
    """Add action context to logger."""
    return logger.bind(action=action)