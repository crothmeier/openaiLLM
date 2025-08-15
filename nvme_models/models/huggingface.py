"""HuggingFace model provider handler."""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional
import logging
import tempfile

from ..validators import Validator, ValidationError, SecurityValidator

logger = logging.getLogger(__name__)


class HuggingFaceHandler:
    """Handles HuggingFace model operations."""
    
    def __init__(self, config: Dict):
        """Initialize HuggingFace handler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.cache_dir = Path(config['providers']['huggingface']['cache_dir'])
        self.models_dir = Path(config['providers']['huggingface']['models_dir'])
        self.use_symlinks = config['providers']['huggingface'].get('use_symlinks', False)
        self.resume_downloads = config['providers']['huggingface'].get('resume_downloads', True)
        
        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Set environment variables
        os.environ['HF_HOME'] = str(self.cache_dir)
        os.environ['TRANSFORMERS_CACHE'] = str(self.cache_dir)
        os.environ['HUGGINGFACE_HUB_CACHE'] = str(self.cache_dir)
    
    def estimate_model_size(self, model_id: str) -> int:
        """Estimate model size in GB.
        
        Args:
            model_id: HuggingFace model ID
            
        Returns:
            int: Estimated size in GB
        """
        # Validate model ID
        try:
            SecurityValidator.validate_model_id(model_id, provider='huggingface')
            logger.debug(f"Model ID validation successful for: {model_id}")
        except ValidationError as e:
            logger.error(f"Model ID validation failed for {model_id}: {e}")
            raise
        try:
            # Try to get model info from HuggingFace API
            import requests
            
            api_url = f"https://huggingface.co/api/models/{model_id}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Try to get size from siblings (files in the repo)
                total_size = 0
                if 'siblings' in data:
                    for file_info in data['siblings']:
                        if 'size' in file_info:
                            total_size += file_info['size']
                
                if total_size > 0:
                    # Convert bytes to GB (rounded up)
                    return max(1, (total_size + (1024**3 - 1)) // (1024**3))
                
                # Try to extract from model card or tags
                if 'tags' in data:
                    for tag in data['tags']:
                        size_gb = Validator.estimate_model_size(tag, 'hf')
                        if size_gb > 1:
                            return size_gb
        except Exception as e:
            logger.debug(f"Could not fetch model info from API: {e}")
        
        # Fallback to pattern-based estimation
        return Validator.estimate_model_size(model_id, 'hf')
    
    def download(self, model_id: str, revision: Optional[str] = None, 
                 token: Optional[str] = None) -> bool:
        """Download a HuggingFace model.
        
        Args:
            model_id: HuggingFace model ID
            revision: Optional revision/branch to download
            token: Optional HuggingFace token for private models
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate model ID with SecurityValidator
            try:
                SecurityValidator.validate_model_id(model_id, provider='huggingface')
                logger.debug(f"Model ID validation successful for: {model_id}")
            except ValidationError as e:
                logger.error(f"Model ID validation failed for {model_id}: {e}")
                raise
            
            # Additional HuggingFace-specific validation
            Validator.validate_hf_model_id(model_id)
            
            # Sanitize model name for filesystem
            model_name = Validator.sanitize_string(model_id.replace('/', '-'))
            
            # Prepare paths
            temp_dir = self.models_dir / f".tmp_{model_name}_{os.getpid()}"
            target_dir = self.models_dir / model_name
            
            # Check if huggingface-cli is available
            if not shutil.which('huggingface-cli'):
                logger.error("huggingface-cli not found. Install with: pip install huggingface-hub")
                return False
            
            # Build download command
            cmd = [
                'huggingface-cli', 'download',
                model_id,
                '--local-dir', str(temp_dir),
                '--local-dir-use-symlinks', 'False' if not self.use_symlinks else 'True'
            ]
            
            if self.resume_downloads:
                cmd.append('--resume-download')
            
            if revision:
                cmd.extend(['--revision', revision])
            
            if token:
                cmd.extend(['--token', token])
            
            logger.info(f"Downloading {model_id} to temporary location...")
            
            # Create temp directory
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # Run download command
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Move to final location atomically
                if target_dir.exists():
                    backup_dir = target_dir.with_suffix(f'.backup.{os.getpid()}')
                    logger.warning(f"Target directory exists, backing up to {backup_dir}")
                    shutil.move(str(target_dir), str(backup_dir))
                
                shutil.move(str(temp_dir), str(target_dir))
                
                # Create model info file
                info_file = target_dir / 'model_info.json'
                with open(info_file, 'w') as f:
                    import time
                    json.dump({
                        'model_id': model_id,
                        'revision': revision,
                        'provider': 'huggingface',
                        'download_date': time.ctime()
                    }, f, indent=2)
                
                logger.info(f"Successfully downloaded {model_id} to {target_dir}")
                
                # Report size
                size = sum(f.stat().st_size for f in target_dir.rglob('*') if f.is_file())
                size_gb = size / (1024**3)
                logger.info(f"Model size: {size_gb:.2f} GB")
                
                return True
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Download failed: {e.stderr}")
                # Clean up temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                return False
                
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            return False
    
    def list_models(self) -> list:
        """List downloaded HuggingFace models.
        
        Returns:
            list: List of model information dictionaries
        """
        models = []
        
        if not self.models_dir.exists():
            return models
        
        for model_dir in self.models_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                model_info = {
                    'name': model_dir.name,
                    'path': str(model_dir),
                    'provider': 'huggingface'
                }
                
                # Try to read model info file
                info_file = model_dir / 'model_info.json'
                if info_file.exists():
                    try:
                        with open(info_file, 'r') as f:
                            stored_info = json.load(f)
                            model_info.update(stored_info)
                    except:
                        pass
                
                # Calculate size
                try:
                    size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                    model_info['size_gb'] = round(size / (1024**3), 2)
                except:
                    model_info['size_gb'] = 0
                
                models.append(model_info)
        
        return models
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a downloaded model.
        
        Args:
            model_name: Model directory name
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Validate model name
        try:
            SecurityValidator.validate_model_id(model_name, provider='huggingface')
            logger.debug(f"Model name validation successful for: {model_name}")
        except ValidationError as e:
            logger.error(f"Model name validation failed for {model_name}: {e}")
            raise
        try:
            model_path = self.models_dir / model_name
            
            if not model_path.exists():
                logger.error(f"Model not found: {model_name}")
                return False
            
            # Create backup first
            backup_path = model_path.with_suffix(f'.deleted.{os.getpid()}')
            shutil.move(str(model_path), str(backup_path))
            
            logger.info(f"Model moved to {backup_path} (can be restored if needed)")
            
            # Schedule actual deletion after confirmation
            logger.info(f"To permanently delete, run: rm -rf {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete model: {e}")
            return False
    
    def verify_model(self, model_name: str) -> Dict:
        """Verify a downloaded model.
        
        Args:
            model_name: Model directory name
            
        Returns:
            Dict: Verification results
        """
        # Validate model name
        try:
            SecurityValidator.validate_model_id(model_name, provider='huggingface')
            logger.debug(f"Model name validation successful for: {model_name}")
        except ValidationError as e:
            logger.error(f"Model name validation failed for {model_name}: {e}")
            raise
        results = {
            'status': 'unknown',
            'checks': []
        }
        
        model_path = self.models_dir / model_name
        
        # Check if model directory exists
        if not model_path.exists():
            results['status'] = 'error'
            results['checks'].append({
                'check': 'exists',
                'status': 'failed',
                'message': f'Model directory not found: {model_name}'
            })
            return results
        
        results['checks'].append({
            'check': 'exists',
            'status': 'passed',
            'message': f'Model directory exists: {model_path}'
        })
        
        # Check for common model files
        model_files = [
            'config.json',
            'tokenizer_config.json',
            'pytorch_model.bin',
            'model.safetensors'
        ]
        
        found_files = []
        for file_name in model_files:
            if (model_path / file_name).exists():
                found_files.append(file_name)
        
        if 'config.json' in found_files:
            results['checks'].append({
                'check': 'config',
                'status': 'passed',
                'message': 'Model configuration found'
            })
        else:
            results['checks'].append({
                'check': 'config',
                'status': 'warning',
                'message': 'config.json not found'
            })
        
        if 'pytorch_model.bin' in found_files or 'model.safetensors' in found_files:
            results['checks'].append({
                'check': 'weights',
                'status': 'passed',
                'message': 'Model weights found'
            })
        else:
            # Check for sharded models
            sharded_files = list(model_path.glob('pytorch_model-*.bin')) + \
                           list(model_path.glob('model-*.safetensors'))
            if sharded_files:
                results['checks'].append({
                    'check': 'weights',
                    'status': 'passed',
                    'message': f'Sharded model weights found ({len(sharded_files)} files)'
                })
            else:
                results['checks'].append({
                    'check': 'weights',
                    'status': 'failed',
                    'message': 'No model weights found'
                })
        
        # Determine overall status
        failed = any(c['status'] == 'failed' for c in results['checks'])
        warnings = any(c['status'] == 'warning' for c in results['checks'])
        
        if failed:
            results['status'] = 'error'
        elif warnings:
            results['status'] = 'warning'
        else:
            results['status'] = 'success'
        
        return results