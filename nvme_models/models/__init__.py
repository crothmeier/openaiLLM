"""Model provider handlers."""

from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def get_provider_handler(provider: str, config: Dict):
    """Get the appropriate provider handler.
    
    Args:
        provider: Provider name ('hf', 'ollama', 'vllm')
        config: Configuration dictionary
        
    Returns:
        Provider handler instance or None
    """
    provider = provider.lower()
    
    if provider in ['hf', 'huggingface']:
        from .huggingface import HuggingFaceHandler
        return HuggingFaceHandler(config)
    elif provider == 'ollama':
        from .ollama import OllamaHandler
        return OllamaHandler(config)
    elif provider == 'vllm':
        from .vllm import VLLMHandler
        return VLLMHandler(config)
    else:
        logger.error(f"Unknown provider: {provider}")
        return None