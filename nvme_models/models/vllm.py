"""vLLM model provider handler."""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Optional, List
import logging

from ..validators import Validator, ValidationError

logger = logging.getLogger(__name__)


class VLLMHandler:
    """Handles vLLM model operations."""
    
    def __init__(self, config: Dict):
        """Initialize vLLM handler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.models_dir = Path(config['providers']['vllm']['models_dir'])
        self.cache_dir = Path(config['providers']['vllm']['cache_dir'])
        
        # Ensure directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Set environment variables for vLLM
        os.environ['VLLM_MODELS_DIR'] = str(self.models_dir)
        os.environ['VLLM_CACHE_DIR'] = str(self.cache_dir)
    
    def estimate_model_size(self, model_id: str) -> int:
        """Estimate model size in GB.
        
        Args:
            model_id: Model identifier (HuggingFace format)
            
        Returns:
            int: Estimated size in GB
        """
        # vLLM typically uses HuggingFace models
        return Validator.estimate_model_size(model_id, 'hf')
    
    def download(self, model_id: str, **kwargs) -> bool:
        """Download a model for vLLM.
        
        vLLM uses HuggingFace models, so this delegates to HF handler.
        
        Args:
            model_id: HuggingFace model ID
            **kwargs: Additional arguments
            
        Returns:
            bool: True if successful, False otherwise
        """
        from .huggingface import HuggingFaceHandler
        
        # Create a temporary HF handler with vLLM paths
        hf_config = self.config.copy()
        hf_config['providers']['huggingface']['models_dir'] = str(self.models_dir)
        
        hf_handler = HuggingFaceHandler(hf_config)
        return hf_handler.download(model_id, **kwargs)
    
    def list_models(self) -> List[Dict]:
        """List vLLM-compatible models.
        
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
                    'provider': 'vllm'
                }
                
                # Check for vLLM compatibility
                config_file = model_dir / 'config.json'
                if config_file.exists():
                    try:
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                            model_info['model_type'] = config.get('model_type', 'unknown')
                            model_info['architectures'] = config.get('architectures', [])
                            
                            # Check if model is vLLM compatible
                            supported_architectures = [
                                'LlamaForCausalLM',
                                'MistralForCausalLM',
                                'GPT2LMHeadModel',
                                'GPTNeoXForCausalLM',
                                'FalconForCausalLM',
                                'MPTForCausalLM',
                                'BaichuanForCausalLM',
                                'QWenLMHeadModel'
                            ]
                            
                            is_compatible = any(
                                arch in supported_architectures 
                                for arch in model_info['architectures']
                            )
                            model_info['vllm_compatible'] = is_compatible
                            
                    except Exception as e:
                        logger.debug(f"Could not read config for {model_dir.name}: {e}")
                
                # Calculate size
                try:
                    size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                    model_info['size_gb'] = round(size / (1024**3), 2)
                except:
                    model_info['size_gb'] = 0
                
                models.append(model_info)
        
        return models
    
    def verify_model(self, model_name: str) -> Dict:
        """Verify a model for vLLM compatibility.
        
        Args:
            model_name: Model directory name
            
        Returns:
            Dict: Verification results
        """
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
        
        # Check for required files
        required_files = ['config.json']
        for file_name in required_files:
            file_path = model_path / file_name
            if file_path.exists():
                results['checks'].append({
                    'check': f'file_{file_name}',
                    'status': 'passed',
                    'message': f'{file_name} found'
                })
            else:
                results['checks'].append({
                    'check': f'file_{file_name}',
                    'status': 'failed',
                    'message': f'{file_name} not found'
                })
        
        # Check vLLM compatibility
        config_file = model_path / 'config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                architectures = config.get('architectures', [])
                supported = [
                    'LlamaForCausalLM',
                    'MistralForCausalLM',
                    'GPT2LMHeadModel',
                    'GPTNeoXForCausalLM',
                    'FalconForCausalLM',
                    'MPTForCausalLM',
                    'BaichuanForCausalLM',
                    'QWenLMHeadModel'
                ]
                
                is_compatible = any(arch in supported for arch in architectures)
                
                if is_compatible:
                    results['checks'].append({
                        'check': 'vllm_compatibility',
                        'status': 'passed',
                        'message': f'Model architecture supported: {architectures}'
                    })
                else:
                    results['checks'].append({
                        'check': 'vllm_compatibility',
                        'status': 'warning',
                        'message': f'Model architecture may not be supported: {architectures}'
                    })
                    
            except Exception as e:
                results['checks'].append({
                    'check': 'vllm_compatibility',
                    'status': 'warning',
                    'message': f'Could not check compatibility: {e}'
                })
        
        # Check for model weights
        weight_files = list(model_path.glob('*.safetensors')) + \
                      list(model_path.glob('*.bin')) + \
                      list(model_path.glob('*.pt'))
        
        if weight_files:
            results['checks'].append({
                'check': 'weights',
                'status': 'passed',
                'message': f'Found {len(weight_files)} weight files'
            })
        else:
            results['checks'].append({
                'check': 'weights',
                'status': 'failed',
                'message': 'No model weight files found'
            })
        
        # Check for tokenizer
        tokenizer_files = ['tokenizer.json', 'tokenizer_config.json', 'tokenizer.model']
        tokenizer_found = any((model_path / f).exists() for f in tokenizer_files)
        
        if tokenizer_found:
            results['checks'].append({
                'check': 'tokenizer',
                'status': 'passed',
                'message': 'Tokenizer files found'
            })
        else:
            results['checks'].append({
                'check': 'tokenizer',
                'status': 'warning',
                'message': 'Tokenizer files not found (may use remote tokenizer)'
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
    
    def generate_server_config(self, model_name: str, **kwargs) -> Dict:
        """Generate vLLM server configuration for a model.
        
        Args:
            model_name: Model directory name
            **kwargs: Additional vLLM server parameters
            
        Returns:
            Dict: vLLM server configuration
        """
        model_path = self.models_dir / model_name
        
        config = {
            'model': str(model_path),
            'download_dir': str(self.cache_dir),
            'tensor_parallel_size': kwargs.get('tensor_parallel_size', 1),
            'gpu_memory_utilization': kwargs.get('gpu_memory_utilization', 0.9),
            'max_model_len': kwargs.get('max_model_len', None),
            'dtype': kwargs.get('dtype', 'auto'),
            'trust_remote_code': kwargs.get('trust_remote_code', False)
        }
        
        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}
        
        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in config:
                config[key] = value
        
        return config
    
    def export_deployment_yaml(self, model_name: str, output_file: str, **kwargs) -> bool:
        """Export Kubernetes deployment YAML for vLLM.
        
        Args:
            model_name: Model directory name
            output_file: Output YAML file path
            **kwargs: Deployment configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            deployment = {
                'apiVersion': 'apps/v1',
                'kind': 'Deployment',
                'metadata': {
                    'name': f'vllm-{model_name}',
                    'labels': {
                        'app': 'vllm',
                        'model': model_name
                    }
                },
                'spec': {
                    'replicas': kwargs.get('replicas', 1),
                    'selector': {
                        'matchLabels': {
                            'app': 'vllm',
                            'model': model_name
                        }
                    },
                    'template': {
                        'metadata': {
                            'labels': {
                                'app': 'vllm',
                                'model': model_name
                            }
                        },
                        'spec': {
                            'containers': [{
                                'name': 'vllm',
                                'image': kwargs.get('image', 'vllm/vllm-openai:latest'),
                                'args': [
                                    '--model', f'/mnt/nvme/models/{model_name}',
                                    '--gpu-memory-utilization', str(kwargs.get('gpu_memory_utilization', 0.9)),
                                    '--tensor-parallel-size', str(kwargs.get('tensor_parallel_size', 1))
                                ],
                                'ports': [{
                                    'containerPort': 8000,
                                    'name': 'http'
                                }],
                                'volumeMounts': [{
                                    'name': 'nvme-storage',
                                    'mountPath': '/mnt/nvme'
                                }],
                                'resources': {
                                    'limits': {
                                        'nvidia.com/gpu': kwargs.get('gpu_count', 1)
                                    }
                                }
                            }],
                            'volumes': [{
                                'name': 'nvme-storage',
                                'hostPath': {
                                    'path': '/mnt/nvme',
                                    'type': 'Directory'
                                }
                            }]
                        }
                    }
                }
            }
            
            import yaml
            with open(output_file, 'w') as f:
                yaml.safe_dump(deployment, f, default_flow_style=False)
            
            logger.info(f"Exported deployment YAML to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export deployment YAML: {e}")
            return False