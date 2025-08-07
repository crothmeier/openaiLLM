"""Ollama model provider handler."""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Optional, List
import logging

from ..validators import Validator, ValidationError

logger = logging.getLogger(__name__)


class OllamaHandler:
    """Handles Ollama model operations."""
    
    def __init__(self, config: Dict):
        """Initialize Ollama handler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.models_dir = Path(config['providers']['ollama']['models_dir'])
        self.default_tag = config['providers']['ollama'].get('default_tag', 'latest')
        
        # Ensure directory exists
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Set environment variable
        os.environ['OLLAMA_MODELS'] = str(self.models_dir)
    
    def estimate_model_size(self, model_name: str) -> int:
        """Estimate model size in GB.
        
        Args:
            model_name: Ollama model name
            
        Returns:
            int: Estimated size in GB
        """
        # Ollama models are typically quantized, so smaller than raw weights
        model_lower = model_name.lower()
        
        # Extract size from model name
        if ':' in model_lower:
            base_model, tag = model_lower.split(':', 1)
        else:
            base_model = model_lower
            tag = self.default_tag
        
        # Common Ollama model sizes (quantized)
        size_map = {
            'llama2': {'7b': 4, '13b': 8, '70b': 40},
            'llama3': {'8b': 5, '70b': 40},
            'mistral': {'7b': 4},
            'mixtral': {'8x7b': 26, '8x22b': 65},
            'codellama': {'7b': 4, '13b': 8, '34b': 20, '70b': 40},
            'phi': {'2.7b': 2},
            'gemma': {'2b': 2, '7b': 5},
            'qwen': {'0.5b': 1, '1.8b': 2, '4b': 3, '7b': 5, '14b': 9, '32b': 20, '72b': 42}
        }
        
        # Try to match model name
        for model_family, sizes in size_map.items():
            if model_family in base_model:
                for size_str, size_gb in sizes.items():
                    if size_str in tag or size_str in base_model:
                        return size_gb
        
        # Fallback to pattern-based estimation
        return Validator.estimate_model_size(model_name, 'ollama')
    
    def check_ollama_service(self) -> bool:
        """Check if Ollama service is running.
        
        Returns:
            bool: True if service is running, False otherwise
        """
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def start_ollama_service(self) -> bool:
        """Start Ollama service if not running.
        
        Returns:
            bool: True if service is running (or was started), False otherwise
        """
        if self.check_ollama_service():
            return True
        
        try:
            logger.info("Starting Ollama service...")
            subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait a moment for service to start
            import time
            time.sleep(2)
            
            return self.check_ollama_service()
            
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {e}")
            return False
    
    def download(self, model_name: str) -> bool:
        """Pull an Ollama model.
        
        Args:
            model_name: Ollama model name (e.g., 'llama2:7b')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate model name
            Validator.validate_ollama_model(model_name)
            
            # Ensure Ollama service is running
            if not self.start_ollama_service():
                logger.error("Ollama service is not running and could not be started")
                logger.info("Try starting it manually with: ollama serve")
                return False
            
            # Add default tag if not specified
            if ':' not in model_name:
                model_name = f"{model_name}:{self.default_tag}"
            
            logger.info(f"Pulling Ollama model: {model_name}")
            
            # Run ollama pull command
            result = subprocess.run(
                ['ollama', 'pull', model_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully pulled {model_name}")
                
                # Try to get actual model size
                list_result = subprocess.run(
                    ['ollama', 'list'],
                    capture_output=True,
                    text=True
                )
                
                if list_result.returncode == 0:
                    for line in list_result.stdout.split('\n'):
                        if model_name in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                logger.info(f"Model size: {parts[1]}")
                
                return True
            else:
                logger.error(f"Failed to pull model: {result.stderr}")
                return False
                
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during pull: {e}")
            return False
    
    def list_models(self) -> List[Dict]:
        """List Ollama models.
        
        Returns:
            list: List of model information dictionaries
        """
        models = []
        
        try:
            if not self.check_ollama_service():
                logger.warning("Ollama service is not running")
                return models
            
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                # Skip header line
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 2:
                            model_info = {
                                'name': parts[0],
                                'size': parts[1] if len(parts) > 1 else 'unknown',
                                'provider': 'ollama',
                                'path': str(self.models_dir)
                            }
                            
                            # Try to parse size to GB
                            size_str = parts[1] if len(parts) > 1 else ''
                            if 'GB' in size_str:
                                try:
                                    model_info['size_gb'] = float(size_str.replace('GB', ''))
                                except:
                                    pass
                            elif 'MB' in size_str:
                                try:
                                    model_info['size_gb'] = float(size_str.replace('MB', '')) / 1024
                                except:
                                    pass
                            
                            # Add modified time if available
                            if len(parts) >= 4:
                                model_info['modified'] = ' '.join(parts[3:])
                            
                            models.append(model_info)
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
        
        return models
    
    def delete_model(self, model_name: str) -> bool:
        """Delete an Ollama model.
        
        Args:
            model_name: Model name to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.check_ollama_service():
                logger.error("Ollama service is not running")
                return False
            
            result = subprocess.run(
                ['ollama', 'rm', model_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully deleted {model_name}")
                return True
            else:
                logger.error(f"Failed to delete model: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete model: {e}")
            return False
    
    def run_model(self, model_name: str, prompt: str, **kwargs) -> Optional[str]:
        """Run inference with an Ollama model.
        
        Args:
            model_name: Model name to run
            prompt: Input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            str: Model output or None if failed
        """
        try:
            if not self.check_ollama_service():
                logger.error("Ollama service is not running")
                return None
            
            # Build command
            cmd = ['ollama', 'run']
            
            # Add parameters
            if 'temperature' in kwargs:
                cmd.extend(['--temperature', str(kwargs['temperature'])])
            
            cmd.extend([model_name, prompt])
            
            # Run command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=kwargs.get('timeout', 60)
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Model run failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Model inference timed out")
            return None
        except Exception as e:
            logger.error(f"Failed to run model: {e}")
            return None
    
    def verify_model(self, model_name: str) -> Dict:
        """Verify an Ollama model.
        
        Args:
            model_name: Model name to verify
            
        Returns:
            Dict: Verification results
        """
        results = {
            'status': 'unknown',
            'checks': []
        }
        
        # Check if Ollama service is running
        if not self.check_ollama_service():
            results['status'] = 'error'
            results['checks'].append({
                'check': 'service',
                'status': 'failed',
                'message': 'Ollama service is not running'
            })
            return results
        
        results['checks'].append({
            'check': 'service',
            'status': 'passed',
            'message': 'Ollama service is running'
        })
        
        # Check if model exists
        models = self.list_models()
        model_found = any(m['name'] == model_name for m in models)
        
        if model_found:
            results['checks'].append({
                'check': 'exists',
                'status': 'passed',
                'message': f'Model {model_name} is available'
            })
            
            # Try to get model info
            try:
                result = subprocess.run(
                    ['ollama', 'show', model_name],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    results['checks'].append({
                        'check': 'info',
                        'status': 'passed',
                        'message': 'Model information retrieved successfully'
                    })
                    results['model_info'] = result.stdout
                else:
                    results['checks'].append({
                        'check': 'info',
                        'status': 'warning',
                        'message': 'Could not retrieve model information'
                    })
            except:
                pass
            
            results['status'] = 'success'
        else:
            results['checks'].append({
                'check': 'exists',
                'status': 'failed',
                'message': f'Model {model_name} not found'
            })
            results['status'] = 'error'
        
        return results