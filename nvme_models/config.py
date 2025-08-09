"""Configuration module for NVMe model storage."""

import os
import yaml
from pathlib import Path
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass


class Config:
    """Manages configuration for NVMe model storage."""
    
    DEFAULT_CONFIG = {
        'storage': {
            'nvme_path': '/mnt/nvme',
            'require_mount': True,
            'min_free_space_gb': 50
        },
        'providers': {
            'huggingface': {
                'cache_dir': '${nvme_path}/hf-cache',
                'models_dir': '${nvme_path}/models',
                'use_symlinks': False,
                'resume_downloads': True
            },
            'ollama': {
                'models_dir': '${nvme_path}/ollama',
                'default_tag': 'latest'
            },
            'vllm': {
                'models_dir': '${nvme_path}/models',
                'cache_dir': '${nvme_path}/vllm-cache'
            }
        },
        'monitoring': {
            'enable_metrics': True,
            'log_level': 'INFO',
            'log_file': '${nvme_path}/logs/nvme-models.log'
        },
        'security': {
            'validate_model_ids': True,
            'allowed_domains': ['huggingface.co', 'ollama.ai'],
            'enable_audit_log': True
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._substitute_variables()
        self._setup_logging()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or use defaults.
        
        Returns:
            Dict: Configuration dictionary
        """
        config = self.DEFAULT_CONFIG.copy()
        
        # Try to load from file
        if self.config_path and Path(self.config_path).exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        config = self._deep_merge(config, file_config)
                        logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
        else:
            # Try default locations
            default_paths = [
                Path.home() / '.config' / 'nvme-models' / 'config.yaml',
                Path('/etc/nvme-models/config.yaml'),
                Path('./config.yaml')
            ]
            
            for path in default_paths:
                if path.exists():
                    try:
                        with open(path, 'r') as f:
                            file_config = yaml.safe_load(f)
                            if file_config:
                                config = self._deep_merge(config, file_config)
                                logger.info(f"Loaded configuration from {path}")
                                break
                    except Exception as e:
                        logger.warning(f"Failed to load config from {path}: {e}")
        
        # Override with environment variables
        config = self._apply_env_overrides(config)
        
        return config
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            update: Dictionary with updates
            
        Returns:
            Dict: Merged dictionary
        """
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _substitute_variables(self):
        """Substitute variables in configuration values."""
        nvme_path = self.config['storage']['nvme_path']
        
        def substitute(obj):
            if isinstance(obj, str):
                return obj.replace('${nvme_path}', nvme_path)
            elif isinstance(obj, dict):
                return {k: substitute(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute(item) for item in obj]
            return obj
        
        self.config = substitute(self.config)
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides to configuration.
        
        Args:
            config: Base configuration
            
        Returns:
            Dict: Configuration with env overrides applied
        """
        # Map of env vars to config paths
        env_mappings = {
            'NVME_PATH': ('storage', 'nvme_path'),
            'NVME_MIN_FREE_SPACE_GB': ('storage', 'min_free_space_gb'),
            'NVME_REQUIRE_MOUNT': ('storage', 'require_mount'),
            'NVME_LOG_LEVEL': ('monitoring', 'log_level'),
            'HF_CACHE_DIR': ('providers', 'huggingface', 'cache_dir'),
            'OLLAMA_MODELS_DIR': ('providers', 'ollama', 'models_dir'),
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Navigate to the correct config location
                current = config
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Set the value with type conversion
                last_key = config_path[-1]
                if last_key.endswith('_gb'):
                    try:
                        current[last_key] = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                elif last_key == 'require_mount' or last_key.startswith('enable_'):
                    current[last_key] = value.lower() in ('true', '1', 'yes')
                else:
                    current[last_key] = value
                
                logger.debug(f"Applied env override {env_var} -> {config_path}")
        
        return config
    
    def _setup_logging(self):
        """Set up logging based on configuration."""
        log_level = self.config['monitoring'].get('log_level', 'INFO')
        log_file = self.config['monitoring'].get('log_file')
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Add file handler if log file is specified
        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                )
                logging.getLogger().addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Failed to set up file logging: {e}")
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a configuration value by key path.
        
        Args:
            *keys: Path to configuration value
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        current = self.config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def set(self, *keys: str, value: Any):
        """Set a configuration value by key path.
        
        Args:
            *keys: Path to configuration value (last arg is the value)
            value: Value to set
        """
        if len(keys) < 1:
            raise ConfigError("At least one key required")
        
        # Navigate to parent
        current = self.config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the value
        current[keys[-1]] = value
    
    def save(self, path: Optional[str] = None):
        """Save configuration to file.
        
        Args:
            path: Path to save to (uses config_path if not specified)
        """
        save_path = path or self.config_path
        if not save_path:
            save_path = Path.home() / '.config' / 'nvme-models' / 'config.yaml'
        
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Saved configuration to {save_path}")
    
    def validate(self) -> bool:
        """Validate the configuration.
        
        Returns:
            bool: True if valid
            
        Raises:
            ConfigError: If configuration is invalid
        """
        from .validators import Validator
        
        try:
            Validator.validate_config(self.config)
            return True
        except Exception as e:
            raise ConfigError(f"Configuration validation failed: {e}")
    
    def to_dict(self) -> Dict:
        """Get configuration as dictionary.
        
        Returns:
            Dict: Configuration dictionary
        """
        return self.config.copy()


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or defaults.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Config: Configuration object
    """
    return Config(config_path)