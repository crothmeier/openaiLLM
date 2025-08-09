"""NVMe storage operations module."""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class NVMeStorageManager:
    """Manages NVMe storage operations for AI models."""
    
    def __init__(self, config: Dict):
        """Initialize NVMe storage manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.nvme_path = Path(config['storage']['nvme_path'])
        self.require_mount = config['storage'].get('require_mount', True)
        self.min_free_space_gb = config['storage'].get('min_free_space_gb', 50)
        
    def check_nvme_mounted(self) -> bool:
        """Check if NVMe is mounted at the configured path.
        
        Returns:
            bool: True if mounted, False otherwise
        """
        try:
            result = subprocess.run(
                ['mountpoint', '-q', str(self.nvme_path)],
                capture_output=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to check mount status: {e}")
            return False
    
    def get_disk_usage(self) -> Dict[str, int]:
        """Get disk usage statistics for NVMe storage.
        
        Returns:
            Dict containing total, used, and available space in GB
        """
        try:
            stat = shutil.disk_usage(self.nvme_path)
            return {
                'total_gb': stat.total // (1024**3),
                'used_gb': stat.used // (1024**3),
                'available_gb': stat.free // (1024**3),
                'usage_percent': (stat.used / stat.total) * 100
            }
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return {'total_gb': 0, 'used_gb': 0, 'available_gb': 0, 'usage_percent': 0}
    
    def check_disk_space(self, required_gb: int) -> bool:
        """Check if sufficient disk space is available.
        
        Args:
            required_gb: Required space in GB
            
        Returns:
            bool: True if sufficient space, False otherwise
        """
        usage = self.get_disk_usage()
        return usage['available_gb'] >= required_gb
    
    def setup_nvme(self) -> bool:
        """Set up NVMe directory structure and environment.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if mounted if required
            if self.require_mount and not self.check_nvme_mounted():
                logger.error(f"NVMe not mounted at {self.nvme_path}")
                return False
            
            # Create directory structure
            directories = [
                self.nvme_path / 'hf-cache',
                self.nvme_path / 'models',
                self.nvme_path / 'ollama'
            ]
            
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            
            # Set up environment variables
            self._setup_environment_variables()
            
            # Create symlinks for compatibility
            self._create_symlinks()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up NVMe: {e}")
            return False
    
    def _setup_environment_variables(self):
        """Set up environment variables for model caching."""
        env_vars = {
            'HF_HOME': str(self.nvme_path / 'hf-cache'),
            'TRANSFORMERS_CACHE': str(self.nvme_path / 'hf-cache'),
            'HUGGINGFACE_HUB_CACHE': str(self.nvme_path / 'hf-cache'),
            'OLLAMA_MODELS': str(self.nvme_path / 'ollama')
        }
        
        # Update current environment
        for key, value in env_vars.items():
            os.environ[key] = value
            logger.info(f"Set {key}={value}")
        
        # Update ~/.bashrc
        bashrc_path = Path.home() / '.bashrc'
        if bashrc_path.exists():
            with open(bashrc_path, 'r') as f:
                content = f.read()
            
            for key, value in env_vars.items():
                export_line = f'export {key}={value}'
                if export_line not in content:
                    with open(bashrc_path, 'a') as f:
                        f.write(f'\n{export_line}')
                    logger.info(f"Added {key} to ~/.bashrc")
    
    def _create_symlinks(self):
        """Create symlinks for backward compatibility."""
        symlinks = [
            (Path.home() / '.cache' / 'huggingface', self.nvme_path / 'hf-cache'),
            (Path.home() / '.ollama', self.nvme_path / 'ollama')
        ]
        
        for link_path, target_path in symlinks:
            try:
                # Create parent directory if needed
                link_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Remove existing file/directory if it exists
                if link_path.exists() and not link_path.is_symlink():
                    if link_path.is_dir():
                        shutil.rmtree(link_path)
                    else:
                        link_path.unlink()
                
                # Create symlink if it doesn't exist
                if not link_path.exists():
                    link_path.symlink_to(target_path)
                    logger.info(f"Created symlink: {link_path} -> {target_path}")
                    
            except Exception as e:
                logger.warning(f"Failed to create symlink {link_path}: {e}")
    
    def verify(self, output_format: str = 'text') -> Dict:
        """Verify NVMe storage configuration.
        
        Args:
            output_format: Output format ('text' or 'json')
            
        Returns:
            Dict containing verification results
        """
        results = {
            'status': 'success',
            'errors': [],
            'warnings': [],
            'success': [],
            'summary': {}
        }
        
        # Check mount status
        if self.check_nvme_mounted():
            results['success'].append({'check': 'mount', 'message': f'{self.nvme_path} is mounted'})
            results['summary']['nvme_mounted'] = True
        else:
            results['errors'].append({'check': 'mount', 'message': f'{self.nvme_path} is not mounted'})
            results['summary']['nvme_mounted'] = False
            results['status'] = 'error'
        
        # Check directories
        directories = ['hf-cache', 'models', 'ollama']
        all_dirs_exist = True
        for dir_name in directories:
            dir_path = self.nvme_path / dir_name
            if dir_path.exists():
                size = self._get_dir_size(dir_path)
                results['success'].append({
                    'check': 'directory',
                    'message': f'{dir_path} exists',
                    'size': size
                })
            else:
                results['errors'].append({
                    'check': 'directory',
                    'message': f'{dir_path} does not exist'
                })
                all_dirs_exist = False
                results['status'] = 'error'
        
        results['summary']['directories_created'] = all_dirs_exist
        
        # Check environment variables
        env_vars = ['HF_HOME', 'TRANSFORMERS_CACHE', 'OLLAMA_MODELS']
        all_env_set = True
        for var in env_vars:
            if os.environ.get(var):
                results['success'].append({
                    'check': 'env_var',
                    'message': f'{var} = {os.environ[var]}'
                })
            else:
                results['warnings'].append({
                    'check': 'env_var',
                    'message': f'{var} is not set'
                })
                all_env_set = False
        
        results['summary']['environment_configured'] = all_env_set
        
        # Check disk usage
        usage = self.get_disk_usage()
        results['summary']['disk_usage'] = usage
        
        if usage['available_gb'] < self.min_free_space_gb:
            results['warnings'].append({
                'check': 'disk_space',
                'message': f'Low disk space: {usage["available_gb"]}GB available'
            })
        else:
            results['success'].append({
                'check': 'disk_space',
                'message': f'Adequate disk space: {usage["available_gb"]}GB available'
            })
        
        # Count model files
        model_count = self._count_model_files()
        results['summary']['model_files_found'] = model_count
        
        if model_count > 0:
            results['success'].append({
                'check': 'models',
                'message': f'Found {model_count} model files'
            })
        else:
            results['warnings'].append({
                'check': 'models',
                'message': 'No model files found yet'
            })
        
        # Set overall status
        if results['errors']:
            results['status'] = 'error'
        elif results['warnings']:
            results['status'] = 'warning'
        
        return results
    
    def _get_dir_size(self, path: Path) -> str:
        """Get human-readable size of a directory.
        
        Args:
            path: Directory path
            
        Returns:
            str: Human-readable size
        """
        try:
            result = subprocess.run(
                ['du', '-sh', str(path)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.split()[0]
        except:
            pass
        return 'unknown'
    
    def _count_model_files(self) -> int:
        """Count model files in NVMe storage.
        
        Returns:
            int: Number of model files
        """
        count = 0
        extensions = ['.safetensors', '.bin', '.gguf', '.pt', '.pth']
        
        try:
            for ext in extensions:
                count += len(list(self.nvme_path.rglob(f'*{ext}')))
        except:
            pass
        
        return count
    
    def download_model(self, provider: str, model_id: str, **kwargs) -> bool:
        """Download a model through the specified provider.
        
        Args:
            provider: Provider name ('hf', 'ollama', etc.)
            model_id: Model identifier
            **kwargs: Additional provider-specific arguments
            
        Returns:
            bool: True if successful, False otherwise
        """
        # This will be implemented by provider-specific handlers
        from .models import get_provider_handler
        
        handler = get_provider_handler(provider, self.config)
        if not handler:
            logger.error(f"Unknown provider: {provider}")
            return False
        
        # Check disk space
        estimated_size = handler.estimate_model_size(model_id)
        required_space = estimated_size * 2  # Need 2x space for download + extraction
        
        if not self.check_disk_space(required_space):
            logger.error(f"Insufficient disk space. Required: {required_space}GB, Available: {self.get_disk_usage()['available_gb']}GB")
            return False
        
        return handler.download(model_id, **kwargs)
    
    def list_models(self) -> List[Dict]:
        """List all downloaded models.
        
        Returns:
            List of model information dictionaries
        """
        models = []
        
        # List models in /mnt/nvme/models
        models_dir = self.nvme_path / 'models'
        if models_dir.exists():
            for model_path in models_dir.iterdir():
                if model_path.is_dir() and not model_path.name.startswith('.'):
                    models.append({
                        'name': model_path.name,
                        'path': str(model_path),
                        'size': self._get_dir_size(model_path),
                        'provider': 'huggingface'
                    })
        
        # List Ollama models
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if parts:
                        models.append({
                            'name': parts[0],
                            'path': str(self.nvme_path / 'ollama'),
                            'size': parts[1] if len(parts) > 1 else 'unknown',
                            'provider': 'ollama'
                        })
        except:
            pass
        
        return models