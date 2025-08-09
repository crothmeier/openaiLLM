"""
LLM Audit Logging Module

Provides async audit logging for LLM interactions with privacy-preserving
hash functions and structured logging via structlog.
"""

import hashlib
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import structlog
import asyncpg

# Configure structured logger for audit events
logger = structlog.get_logger(__name__)


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content for privacy-preserving audit.
    
    Args:
        content: Text content to hash
        
    Returns:
        Hexadecimal SHA-256 hash string
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


async def log_llm_interaction(
    prompt: str,
    response: str,
    metadata: Dict[str, Any]
) -> None:
    """Log LLM interaction for audit purposes.
    
    This function hashes sensitive content, enriches metadata, and logs
    via structlog. A TODO marks where database persistence will be added.
    
    Args:
        prompt: The input prompt sent to the LLM
        response: The response received from the LLM
        metadata: Additional metadata including:
            - model: Model identifier (required)
            - user_id: User identifier (optional)
            - session_id: Session identifier (optional)
            - latency_ms: Request latency in milliseconds (optional)
            - prompt_tokens: Number of prompt tokens (optional)
            - completion_tokens: Number of completion tokens (optional)
            - temperature: Temperature setting (optional)
            - max_tokens: Max tokens setting (optional)
            - status: Request status (success/error/timeout) (optional)
            - error_message: Error message if failed (optional)
            - request_id: Unique request identifier (optional)
            - ip_address: Client IP address (optional)
            - user_agent: Client user agent (optional)
            
    Returns:
        None
        
    Raises:
        ValueError: If required metadata fields are missing
    """
    # Validate required fields
    if 'model' not in metadata:
        raise ValueError("Model identifier is required in metadata")
    
    # Compute hashes for privacy
    prompt_hash = compute_hash(prompt)
    response_hash = compute_hash(response)
    
    # Calculate latency if not provided
    if 'latency_ms' not in metadata and 'start_time' in metadata:
        metadata['latency_ms'] = int((time.time() - metadata['start_time']) * 1000)
    
    # Build audit log entry
    audit_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'prompt_hash': prompt_hash,
        'response_hash': response_hash,
        'model': metadata.get('model'),
        'latency_ms': metadata.get('latency_ms'),
        'user_id': metadata.get('user_id'),
        'session_id': metadata.get('session_id'),
        'status': metadata.get('status', 'success'),
        'prompt_tokens': metadata.get('prompt_tokens'),
        'completion_tokens': metadata.get('completion_tokens'),
        'temperature': metadata.get('temperature'),
        'max_tokens': metadata.get('max_tokens'),
        'top_p': metadata.get('top_p'),
        'request_id': metadata.get('request_id'),
        'ip_address': metadata.get('ip_address'),
        'user_agent': metadata.get('user_agent'),
        'error_message': metadata.get('error_message'),
        'retry_count': metadata.get('retry_count', 0),
        'estimated_cost_usd': metadata.get('estimated_cost_usd'),
        'contains_pii': metadata.get('contains_pii', False),
        'flagged_content': metadata.get('flagged_content', False),
        'moderation_score': metadata.get('moderation_score'),
        'meta': metadata.get('extra_metadata', {})
    }
    
    # Log via structlog (will be picked up by JSON formatter)
    await logger.ainfo(
        "llm_audit",
        **audit_entry
    )
    
    # TODO: Persist to database via asyncpg
    # Implementation will be added in later phase
    # Example implementation:
    # async with asyncpg.create_pool(dsn=DATABASE_URL) as pool:
    #     async with pool.acquire() as conn:
    #         await conn.execute('''
    #             INSERT INTO audit.llm_audit_log (
    #                 prompt_hash, response_hash, model, latency_ms,
    #                 user_id, session_id, status, prompt_tokens,
    #                 completion_tokens, temperature, max_tokens,
    #                 request_id, ip_address, user_agent, meta
    #             ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
    #         ''', prompt_hash, response_hash, audit_entry['model'], ...)


async def log_llm_error(
    prompt: str,
    error: Exception,
    metadata: Dict[str, Any]
) -> None:
    """Log LLM interaction error for audit purposes.
    
    Args:
        prompt: The input prompt that caused the error
        error: The exception that occurred
        metadata: Additional metadata (see log_llm_interaction)
    """
    metadata['status'] = 'error'
    metadata['error_message'] = str(error)
    
    # Use empty response for error cases
    await log_llm_interaction(
        prompt=prompt,
        response="",
        metadata=metadata
    )


async def get_audit_summary(
    start_date: datetime,
    end_date: datetime,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve audit summary statistics.
    
    Args:
        start_date: Start of date range
        end_date: End of date range
        model: Optional model filter
        
    Returns:
        Dictionary containing summary statistics
    """
    # TODO: Implement database query for summary stats
    # Placeholder implementation
    logger.info(
        "audit_summary_requested",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        model=model
    )
    
    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'model': model,
        'total_requests': 0,
        'unique_users': 0,
        'total_tokens': 0,
        'total_cost_usd': 0.0,
        'avg_latency_ms': 0.0,
        'error_rate': 0.0,
        'status': 'pending_implementation'
    }


# Cost estimation helpers
def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> float:
    """Estimate cost based on model and token usage.
    
    Args:
        model: Model identifier
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        
    Returns:
        Estimated cost in USD
    """
    # Simplified cost model - adjust based on actual pricing
    cost_per_1k_tokens = {
        'gpt-4': 0.03,
        'gpt-3.5-turbo': 0.002,
        'claude-3': 0.015,
        'llama-2-7b': 0.001,
        'mistral-7b': 0.001
    }
    
    # Default cost if model not found
    rate = cost_per_1k_tokens.get(model.lower(), 0.001)
    
    total_tokens = prompt_tokens + completion_tokens
    return (total_tokens / 1000.0) * rate


# PII detection helper (simplified)
def check_contains_pii(text: str) -> bool:
    """Simple PII detection check.
    
    Args:
        text: Text to check for PII
        
    Returns:
        True if potential PII detected
    """
    # Simplified regex patterns - enhance for production
    import re
    
    patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone
        r'\b\d{16}\b',  # Credit card
    ]
    
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    
    return False