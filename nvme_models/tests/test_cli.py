"""Test cases for CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from nvme_models.cli import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def temp_config():
    """Create a temporary configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
storage:
  nvme_path: /tmp/test_nvme
  require_mount: false
  min_free_space_gb: 10
providers:
  huggingface:
    cache_dir: ${nvme_path}/hf-cache
    models_dir: ${nvme_path}/models
  ollama:
    models_dir: ${nvme_path}/ollama
  vllm:
    models_dir: ${nvme_path}/models
    cache_dir: ${nvme_path}/vllm-cache
monitoring:
  log_level: INFO
""")
        return f.name


class TestSetupCommand:
    """Test cases for the setup command."""
    
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_setup_success(self, mock_storage_manager, runner, temp_config):
        """Test successful setup command."""
        # Mock storage manager
        mock_storage = Mock()
        mock_storage.setup_nvme.return_value = True
        mock_storage.get_disk_usage.return_value = {
            'available_gb': 100,
            'usage_percent': 50.0
        }
        mock_storage_manager.return_value = mock_storage
        
        result = runner.invoke(cli, ['--config', temp_config, 'setup'])
        
        assert result.exit_code == 0
        assert 'NVMe storage setup complete' in result.output
        mock_storage.setup_nvme.assert_called_once()
    
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_setup_failure(self, mock_storage_manager, runner, temp_config):
        """Test failed setup command."""
        # Mock storage manager
        mock_storage = Mock()
        mock_storage.setup_nvme.return_value = False
        mock_storage_manager.return_value = mock_storage
        
        result = runner.invoke(cli, ['--config', temp_config, 'setup'])
        
        assert result.exit_code == 1
        assert 'Setup failed' in result.output
    
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_setup_no_verify_mount(self, mock_storage_manager, runner, temp_config):
        """Test setup with --no-verify-mount option."""
        mock_storage = Mock()
        mock_storage.setup_nvme.return_value = True
        mock_storage.get_disk_usage.return_value = {
            'available_gb': 100,
            'usage_percent': 50.0
        }
        mock_storage_manager.return_value = mock_storage
        
        result = runner.invoke(cli, ['--config', temp_config, 'setup', '--no-verify-mount'])
        
        assert result.exit_code == 0


class TestVerifyCommand:
    """Test cases for the verify command."""
    
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_verify_text_output(self, mock_storage_manager, runner, temp_config):
        """Test verify command with text output."""
        mock_storage = Mock()
        mock_storage.verify.return_value = {
            'status': 'success',
            'errors': [],
            'warnings': [],
            'success': [
                {'message': 'NVMe is mounted'},
                {'message': 'Directories exist'}
            ],
            'summary': {
                'nvme_mounted': True,
                'directories_created': True,
                'environment_configured': True,
                'disk_usage': {
                    'total_gb': 500,
                    'used_gb': 250,
                    'available_gb': 250,
                    'usage_percent': 50.0
                },
                'model_files_found': 5
            }
        }
        mock_storage_manager.return_value = mock_storage
        
        result = runner.invoke(cli, ['--config', temp_config, 'verify'])
        
        assert result.exit_code == 0
        assert 'NVMe Storage Verification' in result.output
        assert 'All checks passed' in result.output
    
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_verify_json_output(self, mock_storage_manager, runner, temp_config):
        """Test verify command with JSON output."""
        mock_storage = Mock()
        verification_result = {
            'status': 'success',
            'errors': [],
            'warnings': [],
            'success': [{'message': 'Test passed'}],
            'summary': {'nvme_mounted': True}
        }
        mock_storage.verify.return_value = verification_result
        mock_storage_manager.return_value = mock_storage
        
        result = runner.invoke(cli, ['--config', temp_config, 'verify', '--format', 'json'])
        
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert output_json['status'] == 'success'
        assert output_json['summary']['nvme_mounted'] is True
    
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_verify_with_errors(self, mock_storage_manager, runner, temp_config):
        """Test verify command when there are errors."""
        mock_storage = Mock()
        mock_storage.verify.return_value = {
            'status': 'error',
            'errors': [{'message': 'NVMe not mounted'}],
            'warnings': [],
            'success': [],
            'summary': {
                'nvme_mounted': False,
                'directories_created': False
            }
        }
        mock_storage_manager.return_value = mock_storage
        
        result = runner.invoke(cli, ['--config', temp_config, 'verify'])
        
        assert result.exit_code == 1
        assert 'Configuration has errors' in result.output


class TestDownloadCommand:
    """Test cases for the download command."""
    
    @patch('nvme_models.models.get_provider_handler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_download_huggingface_success(self, mock_storage_manager, mock_get_handler, runner, temp_config):
        """Test successful HuggingFace model download."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.check_disk_space.return_value = True
        mock_storage_manager.return_value = mock_storage
        
        # Mock handler
        mock_handler = Mock()
        mock_handler.estimate_model_size.return_value = 10
        mock_handler.download.return_value = True
        mock_handler.list_models.return_value = [
            {'name': 'test-model', 'path': '/test/path', 'size_gb': 10.5}
        ]
        mock_get_handler.return_value = mock_handler
        
        result = runner.invoke(cli, [
            '--config', temp_config,
            'download', 'test-org/test-model',
            '--provider', 'hf'
        ])
        
        assert result.exit_code == 0
        assert 'Successfully downloaded' in result.output
        mock_handler.download.assert_called_once_with('test-org/test-model')
    
    @patch('nvme_models.models.get_provider_handler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_download_insufficient_space(self, mock_storage_manager, mock_get_handler, runner, temp_config):
        """Test download with insufficient disk space."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.check_disk_space.return_value = False
        mock_storage.get_disk_usage.return_value = {'available_gb': 5}
        mock_storage_manager.return_value = mock_storage
        
        # Mock handler
        mock_handler = Mock()
        mock_handler.estimate_model_size.return_value = 10
        mock_get_handler.return_value = mock_handler
        
        result = runner.invoke(cli, [
            '--config', temp_config,
            'download', 'test-model',
            '--provider', 'ollama'
        ])
        
        assert result.exit_code == 1
        assert 'Insufficient disk space' in result.output
    
    @patch('nvme_models.models.get_provider_handler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_download_with_options(self, mock_storage_manager, mock_get_handler, runner, temp_config):
        """Test download with additional options."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.check_disk_space.return_value = True
        mock_storage_manager.return_value = mock_storage
        
        # Mock handler
        mock_handler = Mock()
        mock_handler.estimate_model_size.return_value = 5
        mock_handler.download.return_value = True
        mock_handler.list_models.return_value = []
        mock_get_handler.return_value = mock_handler
        
        result = runner.invoke(cli, [
            '--config', temp_config,
            'download', 'test-model',
            '--provider', 'hf',
            '--revision', 'main',
            '--token', 'test_token'
        ])
        
        assert result.exit_code == 0
        mock_handler.download.assert_called_once_with(
            'test-model',
            revision='main',
            token='test_token'
        )


class TestListCommand:
    """Test cases for the list command."""
    
    @patch('nvme_models.cli.VLLMHandler')
    @patch('nvme_models.cli.OllamaHandler')
    @patch('nvme_models.cli.HuggingFaceHandler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_list_all_models(self, mock_storage_manager, mock_hf, mock_ollama, mock_vllm, runner, temp_config):
        """Test listing all models."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.get_disk_usage.return_value = {
            'used_gb': 100,
            'available_gb': 400
        }
        mock_storage_manager.return_value = mock_storage
        
        # Mock handlers
        mock_hf.return_value.list_models.return_value = [
            {'name': 'hf-model', 'provider': 'huggingface', 'size_gb': 10}
        ]
        mock_ollama.return_value.list_models.return_value = [
            {'name': 'ollama-model', 'provider': 'ollama', 'size': '5GB'}
        ]
        mock_vllm.return_value.list_models.return_value = []
        
        result = runner.invoke(cli, ['--config', temp_config, 'list'])
        
        assert result.exit_code == 0
        assert 'hf-model' in result.output
        assert 'ollama-model' in result.output
    
    @patch('nvme_models.cli.HuggingFaceHandler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_list_filtered_by_provider(self, mock_storage_manager, mock_hf, runner, temp_config):
        """Test listing models filtered by provider."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.get_disk_usage.return_value = {
            'used_gb': 50,
            'available_gb': 450
        }
        mock_storage_manager.return_value = mock_storage
        
        # Mock handler
        mock_hf.return_value.list_models.return_value = [
            {'name': 'hf-model', 'provider': 'huggingface', 'size_gb': 10}
        ]
        
        result = runner.invoke(cli, ['--config', temp_config, 'list', '--provider', 'hf'])
        
        assert result.exit_code == 0
        assert 'hf-model' in result.output
    
    @patch('nvme_models.cli.HuggingFaceHandler')
    @patch('nvme_models.cli.OllamaHandler')
    @patch('nvme_models.cli.VLLMHandler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_list_no_models(self, mock_storage_manager, mock_hf, mock_ollama, mock_vllm, runner, temp_config):
        """Test listing when no models are found."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.return_value = mock_storage
        
        # Mock handlers with empty lists
        mock_hf.return_value.list_models.return_value = []
        mock_ollama.return_value.list_models.return_value = []
        mock_vllm.return_value.list_models.return_value = []
        
        result = runner.invoke(cli, ['--config', temp_config, 'list'])
        
        assert result.exit_code == 0
        assert 'No models found' in result.output


class TestCleanCommand:
    """Test cases for the clean command."""
    
    @patch('pathlib.Path.rglob')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.unlink')
    @patch('shutil.rmtree')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_clean_with_confirmation(self, mock_storage_manager, mock_rmtree, mock_unlink, 
                                    mock_is_dir, mock_rglob, runner, temp_config):
        """Test clean command with user confirmation."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.return_value = mock_storage
        
        # Mock file system
        mock_temp_file = MagicMock()
        mock_temp_file.name = '.tmp_test'
        mock_temp_file.is_dir.return_value = False
        mock_temp_file.stat.return_value.st_size = 1024
        
        mock_rglob.side_effect = [
            [mock_temp_file],  # temp files
            []  # backup files
        ]
        
        result = runner.invoke(cli, ['--config', temp_config, 'clean'], input='y\n')
        
        assert result.exit_code == 0
        assert 'Files to be removed' in result.output
        mock_temp_file.unlink.assert_called_once()
    
    @patch('pathlib.Path.rglob')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_clean_no_files(self, mock_storage_manager, mock_rglob, runner, temp_config):
        """Test clean command when no temporary files exist."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.return_value = mock_storage
        
        # Mock file system with no temp files
        mock_rglob.side_effect = [[], []]
        
        result = runner.invoke(cli, ['--config', temp_config, 'clean'])
        
        assert result.exit_code == 0
        assert 'No temporary files to clean' in result.output


class TestInfoCommand:
    """Test cases for the info command."""
    
    @patch('nvme_models.models.get_provider_handler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_info_model_success(self, mock_storage_manager, mock_get_handler, runner, temp_config):
        """Test info command for existing model."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.return_value = mock_storage
        
        # Mock handler
        mock_handler = Mock()
        mock_handler.verify_model.return_value = {
            'status': 'success',
            'checks': [
                {'message': 'Model exists', 'status': 'passed'},
                {'message': 'Weights found', 'status': 'passed'}
            ]
        }
        mock_get_handler.return_value = mock_handler
        
        result = runner.invoke(cli, [
            '--config', temp_config,
            'info', 'test-model',
            '--provider', 'hf'
        ])
        
        assert result.exit_code == 0
        assert 'Model Information' in result.output
        assert 'Model is ready to use' in result.output
    
    @patch('nvme_models.models.get_provider_handler')
    @patch('nvme_models.cli.NVMeStorageManager')
    def test_info_model_with_warnings(self, mock_storage_manager, mock_get_handler, runner, temp_config):
        """Test info command for model with warnings."""
        # Mock storage
        mock_storage = Mock()
        mock_storage_manager.return_value = mock_storage
        
        # Mock handler
        mock_handler = Mock()
        mock_handler.verify_model.return_value = {
            'status': 'warning',
            'checks': [
                {'message': 'Model exists', 'status': 'passed'},
                {'message': 'Config missing', 'status': 'warning'}
            ]
        }
        mock_get_handler.return_value = mock_handler
        
        result = runner.invoke(cli, [
            '--config', temp_config,
            'info', 'test-model',
            '--provider', 'ollama'
        ])
        
        assert result.exit_code == 0
        assert 'Model has warnings' in result.output