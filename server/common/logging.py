"""
Structured Logging Configuration

Configures structlog for JSON-formatted structured logging across the application.
"""

import sys
import logging
from typing import Any, Dict
import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to all log events.
    
    Args:
        logger: Logger instance
        method_name: Method that was called
        event_dict: Current event dictionary
        
    Returns:
        Enhanced event dictionary with app context
    """
    event_dict['app'] = 'openai-llm'
    event_dict['environment'] = 'production'  # Could be from env var
    return event_dict


def censor_sensitive_data(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Censor sensitive data from logs.
    
    Args:
        logger: Logger instance
        method_name: Method that was called
        event_dict: Current event dictionary
        
    Returns:
        Event dictionary with sensitive data censored
    """
    sensitive_keys = ['password', 'token', 'api_key', 'secret', 'auth']
    
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = '***REDACTED***'
    
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    log_file: str = None,
    json_format: bool = True
) -> None:
    """Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        json_format: Whether to use JSON format (True) or console format (False)
    """
    # Set up stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # Determine processors based on format
    if json_format:
        # Production processors - JSON output
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_app_context,
            censor_sensitive_data,
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development processors - Console output
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_app_context,
            censor_sensitive_data,
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set up file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Audit-specific logging configuration
def configure_audit_logging(audit_log_file: str = "/var/log/openai-llm/audit.jsonl") -> None:
    """Configure separate audit logging stream.
    
    Args:
        audit_log_file: Path to audit log file
    """
    # Create audit logger with separate handler
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't propagate to root logger
    
    # JSON formatter for audit logs
    audit_handler = logging.FileHandler(audit_log_file)
    audit_handler.setFormatter(logging.Formatter('%(message)s'))
    audit_logger.addHandler(audit_handler)
    
    # Configure structlog for audit logger
    audit_processors = [
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
    
    # Create separate structlog configuration for audit
    structlog.configure(
        processors=audit_processors,
        context_class=dict,
        logger_factory=lambda: audit_logger,
        cache_logger_on_first_use=True,
    )


# Example usage and initialization
if __name__ == "__main__":
    # Configure main application logging
    configure_logging(
        log_level="INFO",
        json_format=True
    )
    
    # Configure audit logging
    configure_audit_logging()
    
    # Example log entries
    logger = get_logger(__name__)
    
    logger.info("application_started", version="1.0.0")
    logger.warning("resource_warning", resource="memory", usage_percent=85.5)
    logger.error("processing_failed", error="Connection timeout", retry_count=3)
    
    # Example with sensitive data (will be redacted)
    logger.info("api_call", api_key="sk-12345", endpoint="/v1/completions")