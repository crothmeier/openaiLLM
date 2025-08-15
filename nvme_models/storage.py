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
        
    def check_nvme_mounted(self) -> Tuple[bool, Optional[Dict[str, str]]]:
        """Check if NVMe is mounted at the configured path with detailed verification.
        
        Returns:
            Tuple[bool, Optional[Dict]]: (is_mounted, error_details)
                - is_mounted: True if properly mounted NVMe, False otherwise
                - error_details: Dict with error information if check fails, None if successful
        """
        error_details = {}
        
        try:
            # Step 1: Check if path exists
            if not self.nvme_path.exists():
                error_msg = f"Path does not exist: {self.nvme_path}"
                logger.error(error_msg)
                error_details['error'] = 'path_not_found'
                error_details['message'] = error_msg
                error_details['path'] = str(self.nvme_path)
                return False, error_details
            
            # Step 2: Check if it's a directory
            if not self.nvme_path.is_dir():
                error_msg = f"Path exists but is not a directory: {self.nvme_path}"
                logger.error(error_msg)
                error_details['error'] = 'not_a_directory'
                error_details['message'] = error_msg
                error_details['path'] = str(self.nvme_path)
                return False, error_details
            
            # Step 3: Check if it's actually mounted
            try:
                result = subprocess.run(
                    ['mountpoint', '-q', str(self.nvme_path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode != 0:
                    # Not a mount point - get more info
                    mount_check = subprocess.run(
                        ['mount'], 
                        capture_output=True, 
                        text=True,
                        timeout=5
                    )
                    
                    # Check if path appears in mount output
                    is_mounted = str(self.nvme_path) in mount_check.stdout
                    
                    if not is_mounted:
                        error_msg = f"Path exists but is not mounted: {self.nvme_path}"
                        logger.warning(error_msg)
                        error_details['error'] = 'not_mounted'
                        error_details['message'] = error_msg
                        error_details['path'] = str(self.nvme_path)
                        # Don't return yet, check if it might be an NVMe device anyway
                    
            except subprocess.TimeoutExpired:
                error_msg = "Mount check command timed out"
                logger.error(error_msg)
                error_details['error'] = 'mount_check_timeout'
                error_details['message'] = error_msg
                return False, error_details
            except Exception as e:
                error_msg = f"Failed to run mountpoint command: {e}"
                logger.error(error_msg)
                error_details['error'] = 'mount_check_failed'
                error_details['message'] = error_msg
                error_details['exception'] = str(e)
                # Continue to device check anyway
            
            # Step 4: Verify it's an NVMe device
            is_nvme = False
            device_info = {}
            
            try:
                # Get device for mount point
                df_result = subprocess.run(
                    ['df', str(self.nvme_path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if df_result.returncode == 0:
                    lines = df_result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        # Extract device from df output
                        device = lines[1].split()[0]
                        device_info['device'] = device
                        
                        # Check if device is NVMe
                        if 'nvme' in device.lower():
                            is_nvme = True
                            logger.info(f"Detected NVMe device from path: {device}")
                        else:
                            # Check /sys/block for NVMe indicators
                            sys_block_path = Path('/sys/block')
                            if sys_block_path.exists():
                                for block_dev in sys_block_path.iterdir():
                                    if 'nvme' in block_dev.name:
                                        model_path = block_dev / 'device' / 'model'
                                        if model_path.exists():
                                            try:
                                                model = model_path.read_text().strip()
                                                device_info['model'] = model
                                                # Check if this device is related to our mount
                                                dev_path = f"/dev/{block_dev.name}"
                                                if dev_path in device or device.startswith(dev_path):
                                                    is_nvme = True
                                                    logger.info(f"Found NVMe device: {block_dev.name} - Model: {model}")
                                                    break
                                            except Exception as e:
                                                logger.debug(f"Could not read model for {block_dev.name}: {e}")
                
                if not is_nvme:
                    # Try alternative method: check lsblk
                    try:
                        lsblk_result = subprocess.run(
                            ['lsblk', '-o', 'NAME,TYPE,MOUNTPOINT', '-J'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if lsblk_result.returncode == 0:
                            import json
                            lsblk_data = json.loads(lsblk_result.stdout)
                            
                            # Search for our mount point in the tree
                            def find_mount(devices, mount_path):
                                for device in devices:
                                    if device.get('mountpoint') == str(mount_path):
                                        return device
                                    if 'children' in device:
                                        found = find_mount(device['children'], mount_path)
                                        if found:
                                            return found
                                return None
                            
                            mount_device = find_mount(lsblk_data.get('blockdevices', []), self.nvme_path)
                            if mount_device and 'nvme' in mount_device.get('name', '').lower():
                                is_nvme = True
                                device_info['lsblk_device'] = mount_device.get('name')
                                logger.info(f"Found NVMe device via lsblk: {mount_device.get('name')}")
                    
                    except Exception as e:
                        logger.debug(f"Could not check lsblk: {e}")
                
            except subprocess.TimeoutExpired:
                logger.warning("Device check timed out, assuming not NVMe")
            except Exception as e:
                logger.warning(f"Could not verify NVMe device: {e}")
            
            # Final determination
            if result.returncode == 0 and is_nvme:
                logger.info(f"Successfully verified NVMe mount at {self.nvme_path}")
                return True, None
            elif result.returncode == 0 and not is_nvme:
                warning_msg = f"Path is mounted but not detected as NVMe device: {self.nvme_path}"
                logger.warning(warning_msg)
                error_details['warning'] = 'not_nvme_device'
                error_details['message'] = warning_msg
                error_details['device_info'] = device_info
                # Return True if mounted (even if not confirmed NVMe)
                return True, error_details
            else:
                # Not mounted
                if not error_details:
                    error_details['error'] = 'mount_verification_failed'
                    error_details['message'] = f"Mount verification failed for {self.nvme_path}"
                error_details['device_info'] = device_info
                return False, error_details
                
        except Exception as e:
            error_msg = f"Unexpected error checking NVMe mount: {e}"
            logger.error(error_msg)
            error_details['error'] = 'unexpected_error'
            error_details['message'] = error_msg
            error_details['exception'] = str(type(e).__name__)
            error_details['details'] = str(e)
            return False, error_details
    
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
            if self.require_mount:
                is_mounted, error_details = self.check_nvme_mounted()
                if not is_mounted:
                    logger.error(f"NVMe not mounted at {self.nvme_path}")
                    if error_details:
                        logger.error(f"Mount check details: {error_details}")
                    return False
                elif error_details and 'warning' in error_details:
                    logger.warning(f"Mount check warning: {error_details.get('message', 'Unknown warning')}")
            
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
        is_mounted, mount_details = self.check_nvme_mounted()
        if is_mounted:
            if mount_details and 'warning' in mount_details:
                results['warnings'].append({
                    'check': 'mount',
                    'message': mount_details.get('message', 'Mount check had warnings'),
                    'details': mount_details
                })
                results['summary']['nvme_mounted'] = True
                results['summary']['mount_warning'] = mount_details.get('warning')
            else:
                results['success'].append({'check': 'mount', 'message': f'{self.nvme_path} is mounted as NVMe'})
                results['summary']['nvme_mounted'] = True
        else:
            error_msg = mount_details.get('message', f'{self.nvme_path} is not mounted') if mount_details else f'{self.nvme_path} is not mounted'
            results['errors'].append({
                'check': 'mount',
                'message': error_msg,
                'details': mount_details
            })
            results['summary']['nvme_mounted'] = False
            results['summary']['mount_error'] = mount_details.get('error') if mount_details else 'unknown'
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