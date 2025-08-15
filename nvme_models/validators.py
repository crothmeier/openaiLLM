"""Input validation module for NVMe model storage."""

import re
import os
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class Validator:
    """Validates inputs for NVMe model storage operations."""
    
    # Patterns for validating model identifiers
    HF_MODEL_PATTERN = re.compile(r'^[\w\-\.]+/[\w\-\.]+$')
    OLLAMA_MODEL_PATTERN = re.compile(r'^[\w\-\.:]+$')
    SAFE_PATH_PATTERN = re.compile(r'^[\w\-\./]+$')
    
    @classmethod
    def validate_hf_model_id(cls, model_id: str) -> bool:
        """Validate HuggingFace model ID format.
        
        Args:
            model_id: HuggingFace model ID (e.g., 'meta-llama/Llama-2-7b-hf')
            
        Returns:
            bool: True if valid, False otherwise
            
        Raises:
            ValidationError: If model ID is invalid
        """
        if not model_id:
            raise ValidationError("Model ID cannot be empty")
        
        if not cls.HF_MODEL_PATTERN.match(model_id):
            raise ValidationError(
                f"Invalid HuggingFace model ID format: {model_id}. "
                "Expected format: 'organization/model-name'"
            )
        
        # Check for suspicious patterns
        if '..' in model_id or model_id.startswith('/'):
            raise ValidationError(f"Suspicious path pattern in model ID: {model_id}")
        
        return True
    
    @classmethod
    def validate_ollama_model(cls, model_name: str) -> bool:
        """Validate Ollama model name format.
        
        Args:
            model_name: Ollama model name (e.g., 'llama2:7b')
            
        Returns:
            bool: True if valid, False otherwise
            
        Raises:
            ValidationError: If model name is invalid
        """
        if not model_name:
            raise ValidationError("Model name cannot be empty")
        
        if not cls.OLLAMA_MODEL_PATTERN.match(model_name):
            raise ValidationError(
                f"Invalid Ollama model name format: {model_name}. "
                "Expected format: 'model-name' or 'model-name:tag'"
            )
        
        # Check for suspicious patterns
        if '..' in model_name or model_name.startswith('/'):
            raise ValidationError(f"Suspicious path pattern in model name: {model_name}")
        
        return True
    
    @classmethod
    def validate_path(cls, path: str, base_path: Optional[str] = None) -> Path:
        """Validate and sanitize a file system path.
        
        Args:
            path: Path to validate
            base_path: Optional base path to ensure path is within
            
        Returns:
            Path: Validated Path object
            
        Raises:
            ValidationError: If path is invalid or outside base_path
        """
        try:
            validated_path = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid path: {path} - {e}")
        
        # Check if path exists (for read operations)
        # Note: We don't check existence for write operations
        
        # If base_path is provided, ensure path is within it
        if base_path:
            try:
                base = Path(base_path).resolve()
                if not str(validated_path).startswith(str(base)):
                    raise ValidationError(
                        f"Path {validated_path} is outside allowed base path {base}"
                    )
            except Exception as e:
                raise ValidationError(f"Invalid base path: {base_path} - {e}")
        
        return validated_path
    
    @classmethod
    def validate_write_directory(cls, directory: str, base_path: str = "/mnt/nvme") -> Path:
        """Validate a directory for write operations.
        
        Args:
            directory: Directory path to validate
            base_path: Base path that directory must be within
            
        Returns:
            Path: Validated directory Path object
            
        Raises:
            ValidationError: If directory is invalid or not writable
        """
        dir_path = cls.validate_path(directory, base_path)
        
        # Check if directory exists and is writable
        if dir_path.exists():
            if not dir_path.is_dir():
                raise ValidationError(f"Path exists but is not a directory: {dir_path}")
            if not os.access(dir_path, os.W_OK):
                raise ValidationError(f"Directory is not writable: {dir_path}")
        else:
            # Check if parent directory is writable
            parent = dir_path.parent
            if not parent.exists():
                raise ValidationError(f"Parent directory does not exist: {parent}")
            if not os.access(parent, os.W_OK):
                raise ValidationError(f"Cannot create directory in: {parent}")
        
        return dir_path
    
    @classmethod
    def validate_env_vars(cls) -> bool:
        """Validate required environment variables are set.
        
        Returns:
            bool: True if all required env vars are set
            
        Raises:
            ValidationError: If required env vars are missing
        """
        required_vars = ['HF_HOME', 'TRANSFORMERS_CACHE', 'OLLAMA_MODELS']
        missing_vars = []
        
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValidationError(
                f"Required environment variables not set: {', '.join(missing_vars)}. "
                "Run 'nvme-models setup' first."
            )
        
        return True
    
    @classmethod
    def sanitize_string(cls, input_string: str, max_length: int = 255) -> str:
        """Sanitize a string for safe use in file paths and commands.
        
        Args:
            input_string: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized string
        """
        # Remove or replace dangerous characters
        sanitized = re.sub(r'[^\w\-\.]', '_', input_string)
        
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Ensure not empty
        if not sanitized:
            sanitized = "unnamed"
        
        return sanitized
    
    @classmethod
    def validate_disk_space(cls, required_gb: int, path: str = "/mnt/nvme") -> bool:
        """Validate sufficient disk space is available.
        
        Args:
            required_gb: Required space in GB
            path: Path to check space for
            
        Returns:
            bool: True if sufficient space available
            
        Raises:
            ValidationError: If insufficient space
        """
        import shutil
        
        try:
            stat = shutil.disk_usage(path)
            available_gb = stat.free // (1024**3)
            
            if available_gb < required_gb:
                raise ValidationError(
                    f"Insufficient disk space. Required: {required_gb}GB, "
                    f"Available: {available_gb}GB"
                )
            
            return True
            
        except Exception as e:
            raise ValidationError(f"Failed to check disk space: {e}")
    
    @classmethod
    def validate_config(cls, config: dict) -> bool:
        """Validate configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If configuration is invalid
        """
        # Check required sections
        required_sections = ['storage', 'providers']
        for section in required_sections:
            if section not in config:
                raise ValidationError(f"Missing required config section: {section}")
        
        # Validate storage section
        storage = config['storage']
        if 'nvme_path' not in storage:
            raise ValidationError("Missing 'nvme_path' in storage configuration")
        
        # Validate nvme_path
        cls.validate_path(storage['nvme_path'])
        
        # Validate providers section
        providers = config['providers']
        if not isinstance(providers, dict):
            raise ValidationError("'providers' section must be a dictionary")
        
        return True
    
    @classmethod
    def estimate_model_size(cls, model_id: str, provider: str = 'hf') -> int:
        """Estimate model size in GB based on model ID.
        
        Args:
            model_id: Model identifier
            provider: Provider type ('hf', 'ollama')
            
        Returns:
            int: Estimated size in GB
        """
        # Extract size hints from model name
        model_lower = model_id.lower()
        
        # Common size patterns
        size_patterns = [
            (r'(\d+)b', 1),  # e.g., "7b" -> multiply by 1
            (r'(\d+\.\d+)b', 1),  # e.g., "6.7b" -> multiply by 1
            (r'(\d+)m', 0.001),  # e.g., "350m" -> multiply by 0.001
        ]
        
        for pattern, multiplier in size_patterns:
            match = re.search(pattern, model_lower)
            if match:
                size = float(match.group(1))
                # Rough estimate: 2GB per billion parameters for fp16
                return max(1, int(size * multiplier * 2))
        
        # Provider-specific defaults
        if provider == 'ollama':
            # Ollama models are typically quantized
            if '70b' in model_lower:
                return 40  # Quantized 70B
            elif '33b' in model_lower or '30b' in model_lower:
                return 20  # Quantized 30-33B
            elif '13b' in model_lower:
                return 8  # Quantized 13B
            elif '7b' in model_lower:
                return 4  # Quantized 7B
        
        # Default conservative estimate
        return 10


class SecurityValidator:
    """Security-focused validation for inputs to prevent common vulnerabilities."""
    
    @staticmethod
    def validate_path_traversal(path: str) -> bool:
        """Validate that a path doesn't contain directory traversal attempts.
        
        Args:
            path: Path string to validate
            
        Returns:
            bool: False if path contains traversal patterns or absolute paths, True otherwise
        """
        # Check for directory traversal patterns
        if '../' in path or '..\\' in path:
            return False
        
        # Check for absolute paths (Unix)
        if path.startswith('/'):
            return False
        
        # Check for Windows drive letters
        if len(path) >= 2 and path[1] == ':':
            # Check for patterns like C:, D:, etc.
            if path[0].isalpha():
                return False
        
        # Check for UNC paths (Windows network paths)
        if path.startswith('\\\\'):
            return False
        
        return True
    
    @staticmethod
    def validate_command_injection(input_str: str) -> bool:
        """Validate that input doesn't contain shell metacharacters.
        
        Args:
            input_str: Input string to validate
            
        Returns:
            bool: False if input contains dangerous shell metacharacters, True otherwise
        """
        # Define dangerous shell metacharacters
        dangerous_chars = [
            ';',   # Command separator
            '|',   # Pipe
            '&',   # Background/command separator
            '$',   # Variable expansion
            '`',   # Command substitution
            '(',   # Subshell
            ')',   # Subshell
            '{',   # Command grouping
            '}',   # Command grouping
            '<',   # Input redirection
            '>',   # Output redirection
            '\n',  # Newline
            '\r',  # Carriage return
        ]
        
        # Check for presence of any dangerous character
        for char in dangerous_chars:
            if char in input_str:
                return False
        
        return True
    
    @staticmethod
    def sanitize_for_filesystem(name: str) -> str:
        """Sanitize a string for safe use as a filesystem name.
        
        Args:
            name: String to sanitize
            
        Returns:
            str: Sanitized string safe for filesystem use
        """
        # Remove leading/trailing spaces and dots
        name = name.strip(' .')
        
        # Replace characters not in allowed set with underscores
        # Allowed: alphanumeric, dot, underscore, hyphen
        sanitized = re.sub(r'[^a-zA-Z0-9._\-]', '_', name)
        
        # Remove leading dots (hidden files) and trailing dots
        sanitized = sanitized.lstrip('.').rstrip('.')
        
        # Limit length to 255 characters (common filesystem limit)
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        # If empty after sanitization, provide a default
        if not sanitized:
            sanitized = 'unnamed'
        
        return sanitized
    
    @staticmethod
    def validate_model_id(model_id: str, provider: str) -> Tuple[bool, str]:
        """Validate model ID based on provider-specific patterns.
        
        Args:
            model_id: Model identifier to validate
            provider: Provider type ('huggingface' or 'ollama')
            
        Returns:
            tuple: (is_valid, error_message) where error_message is empty if valid
        """
        # Check for empty model ID
        if not model_id:
            error_msg = "Model ID cannot be empty"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg
        
        # Check length constraint
        if len(model_id) > 256:
            error_msg = f"Model ID exceeds maximum length of 256 characters: {len(model_id)}"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg
        
        # Check for command injection attempts
        dangerous_chars = [';', '|', '&', '$', '`', '(', ')', '{', '}', '<', '>', '\n', '\r', '\0']
        for char in dangerous_chars:
            if char in model_id:
                error_msg = f"Model ID contains dangerous character '{char}': potential command injection attempt"
                logger.warning(f"Validation failed: {error_msg}")
                return False, error_msg
        
        # Check for path traversal attempts
        if '..' in model_id or model_id.startswith('/') or model_id.startswith('\\'):
            error_msg = f"Model ID contains path traversal pattern: {model_id}"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg
        
        # Provider-specific validation
        if provider.lower() == 'huggingface':
            # HuggingFace pattern: organization/model-name
            pattern = re.compile(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$')
            if not pattern.match(model_id):
                error_msg = f"Invalid HuggingFace model ID format: {model_id}. Expected pattern: 'organization/model-name'"
                logger.warning(f"Validation failed: {error_msg}")
                return False, error_msg
        elif provider.lower() == 'ollama':
            # Ollama pattern: model-name or model-name:tag
            pattern = re.compile(r'^[a-zA-Z0-9_-]+(:[a-zA-Z0-9._-]+)?$')
            if not pattern.match(model_id):
                error_msg = f"Invalid Ollama model ID format: {model_id}. Expected pattern: 'model-name' or 'model-name:tag'"
                logger.warning(f"Validation failed: {error_msg}")
                return False, error_msg
        else:
            error_msg = f"Unknown provider: {provider}. Supported providers: 'huggingface', 'ollama'"
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg
        
        return True, ""