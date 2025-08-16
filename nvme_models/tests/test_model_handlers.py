"""Tests for model handler security validation."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
from pathlib import Path

from nvme_models.validators import ValidationError
from nvme_models.models.huggingface import HuggingFaceHandler
from nvme_models.models.ollama import OllamaHandler
from nvme_models.models.vllm import VLLMHandler


class TestHuggingFaceHandler(unittest.TestCase):
    """Test HuggingFace handler security validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'providers': {
                'huggingface': {
                    'cache_dir': f'{self.temp_dir}/cache',
                    'models_dir': f'{self.temp_dir}/models',
                    'use_symlinks': False,
                    'resume_downloads': True
                }
            }
        }
        self.handler = HuggingFaceHandler(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_estimate_model_size_valid(self, mock_validate):
        """Test estimate_model_size with valid model ID."""
        mock_validate.return_value = None  # No exception means valid
        
        # Should not raise an exception
        size = self.handler.estimate_model_size('bert-base-uncased')
        self.assertIsInstance(size, int)
        mock_validate.assert_called_once_with('bert-base-uncased', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_estimate_model_size_invalid(self, mock_validate):
        """Test estimate_model_size with invalid model ID."""
        mock_validate.side_effect = ValidationError("Invalid model ID: contains path traversal")
        
        with self.assertRaises(ValidationError) as context:
            self.handler.estimate_model_size('../invalid/model')
        
        self.assertIn("Invalid model ID", str(context.exception))
        mock_validate.assert_called_once_with('../invalid/model', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.subprocess.run')
    @patch('nvme_models.models.huggingface.shutil.which')
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_download_valid_model(self, mock_validate, mock_which, mock_run):
        """Test download with valid model ID."""
        mock_validate.return_value = None
        mock_which.return_value = '/usr/bin/huggingface-cli'
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
        
        result = self.handler.download('facebook/opt-125m')
        self.assertTrue(result)
        mock_validate.assert_called_once_with('facebook/opt-125m', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_download_invalid_model(self, mock_validate):
        """Test download with invalid model ID."""
        mock_validate.side_effect = ValidationError("Invalid model ID")
        
        result = self.handler.download('../../etc/passwd')
        self.assertFalse(result)
        mock_validate.assert_called_once_with('../../etc/passwd', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_delete_model_valid(self, mock_validate):
        """Test delete_model with valid model name."""
        mock_validate.return_value = None
        
        # Create a mock model directory
        model_dir = Path(self.temp_dir) / 'models' / 'test-model'
        model_dir.mkdir(parents=True)
        
        result = self.handler.delete_model('test-model')
        self.assertTrue(result)
        mock_validate.assert_called_once_with('test-model', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_delete_model_invalid(self, mock_validate):
        """Test delete_model with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.delete_model('../../../etc/passwd')
        
        mock_validate.assert_called_once_with('../../../etc/passwd', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_verify_model_valid(self, mock_validate):
        """Test verify_model with valid model name."""
        mock_validate.return_value = None
        
        # Create a mock model directory with config
        model_dir = Path(self.temp_dir) / 'models' / 'test-model'
        model_dir.mkdir(parents=True)
        (model_dir / 'config.json').write_text('{}')
        
        result = self.handler.verify_model('test-model')
        self.assertIsInstance(result, dict)
        self.assertIn('status', result)
        mock_validate.assert_called_once_with('test-model', provider='huggingface')
    
    @patch('nvme_models.models.huggingface.SecurityValidator.validate_model_id')
    def test_verify_model_invalid(self, mock_validate):
        """Test verify_model with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.verify_model('../../malicious')
        
        mock_validate.assert_called_once_with('../../malicious', provider='huggingface')


class TestOllamaHandler(unittest.TestCase):
    """Test Ollama handler security validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'providers': {
                'ollama': {
                    'models_dir': f'{self.temp_dir}/models',
                    'default_tag': 'latest'
                }
            }
        }
        self.handler = OllamaHandler(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_estimate_model_size_valid(self, mock_validate):
        """Test estimate_model_size with valid model name."""
        mock_validate.return_value = None
        
        size = self.handler.estimate_model_size('llama2:7b')
        self.assertIsInstance(size, int)
        mock_validate.assert_called_once_with('llama2:7b', provider='ollama')
    
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_estimate_model_size_invalid(self, mock_validate):
        """Test estimate_model_size with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.estimate_model_size('../malicious:tag')
        
        mock_validate.assert_called_once_with('../malicious:tag', provider='ollama')
    
    @patch('nvme_models.models.ollama.subprocess.run')
    @patch('nvme_models.models.ollama.OllamaHandler.start_ollama_service')
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_download_valid_model(self, mock_validate, mock_start_service, mock_run):
        """Test download with valid model name."""
        mock_validate.return_value = None
        mock_start_service.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
        
        result = self.handler.download('llama2:7b')
        self.assertTrue(result)
        mock_validate.assert_called_once_with('llama2:7b', provider='ollama')
    
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_download_invalid_model(self, mock_validate):
        """Test download with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        result = self.handler.download('../../etc/passwd')
        self.assertFalse(result)
        mock_validate.assert_called_once_with('../../etc/passwd', provider='ollama')
    
    @patch('nvme_models.models.ollama.subprocess.run')
    @patch('nvme_models.models.ollama.OllamaHandler.check_ollama_service')
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_delete_model_valid(self, mock_validate, mock_check_service, mock_run):
        """Test delete_model with valid model name."""
        mock_validate.return_value = None
        mock_check_service.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout='', stderr='')
        
        result = self.handler.delete_model('llama2:7b')
        self.assertTrue(result)
        mock_validate.assert_called_once_with('llama2:7b', provider='ollama')
    
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_delete_model_invalid(self, mock_validate):
        """Test delete_model with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.delete_model('../../malicious')
        
        mock_validate.assert_called_once_with('../../malicious', provider='ollama')
    
    @patch('nvme_models.models.ollama.OllamaHandler.check_ollama_service')
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_run_model_valid(self, mock_validate, mock_check_service):
        """Test run_model with valid model name."""
        mock_validate.return_value = None
        mock_check_service.return_value = False  # Service not running
        
        result = self.handler.run_model('llama2:7b', 'Hello world')
        self.assertIsNone(result)  # Service not running
        mock_validate.assert_called_once_with('llama2:7b', provider='ollama')
    
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_run_model_invalid(self, mock_validate):
        """Test run_model with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.run_model('../../../etc/passwd', 'test prompt')
        
        mock_validate.assert_called_once_with('../../../etc/passwd', provider='ollama')
    
    @patch('nvme_models.models.ollama.OllamaHandler.list_models')
    @patch('nvme_models.models.ollama.OllamaHandler.check_ollama_service')
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_verify_model_valid(self, mock_validate, mock_check_service, mock_list):
        """Test verify_model with valid model name."""
        mock_validate.return_value = None
        mock_check_service.return_value = True
        mock_list.return_value = [{'name': 'llama2:7b'}]
        
        result = self.handler.verify_model('llama2:7b')
        self.assertIsInstance(result, dict)
        self.assertIn('status', result)
        mock_validate.assert_called_once_with('llama2:7b', provider='ollama')
    
    @patch('nvme_models.models.ollama.SecurityValidator.validate_model_id')
    def test_verify_model_invalid(self, mock_validate):
        """Test verify_model with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.verify_model('../../malicious')
        
        mock_validate.assert_called_once_with('../../malicious', provider='ollama')


class TestVLLMHandler(unittest.TestCase):
    """Test vLLM handler security validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'providers': {
                'vllm': {
                    'models_dir': f'{self.temp_dir}/models',
                    'cache_dir': f'{self.temp_dir}/cache'
                },
                'huggingface': {
                    'cache_dir': f'{self.temp_dir}/hf_cache',
                    'models_dir': f'{self.temp_dir}/hf_models'
                }
            }
        }
        self.handler = VLLMHandler(self.config)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_estimate_model_size_valid(self, mock_validate):
        """Test estimate_model_size with valid model ID."""
        mock_validate.return_value = None
        
        size = self.handler.estimate_model_size('facebook/opt-125m')
        self.assertIsInstance(size, int)
        mock_validate.assert_called_once_with('facebook/opt-125m', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_estimate_model_size_invalid(self, mock_validate):
        """Test estimate_model_size with invalid model ID."""
        mock_validate.side_effect = ValidationError("Invalid model ID")
        
        with self.assertRaises(ValidationError):
            self.handler.estimate_model_size('../../../etc/passwd')
        
        mock_validate.assert_called_once_with('../../../etc/passwd', provider='vllm')
    
    @patch('nvme_models.models.huggingface.HuggingFaceHandler.download')
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_download_valid_model(self, mock_validate, mock_hf_download):
        """Test download with valid model ID."""
        mock_validate.return_value = None
        mock_hf_download.return_value = True
        
        result = self.handler.download('facebook/opt-125m')
        self.assertTrue(result)
        mock_validate.assert_called_once_with('facebook/opt-125m', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_download_invalid_model(self, mock_validate):
        """Test download with invalid model ID."""
        mock_validate.side_effect = ValidationError("Invalid model ID")
        
        with self.assertRaises(ValidationError):
            self.handler.download('../../malicious/model')
        
        mock_validate.assert_called_once_with('../../malicious/model', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_verify_model_valid(self, mock_validate):
        """Test verify_model with valid model name."""
        mock_validate.return_value = None
        
        # Create a mock model directory
        model_dir = Path(self.temp_dir) / 'models' / 'test-model'
        model_dir.mkdir(parents=True)
        (model_dir / 'config.json').write_text('{"architectures": ["LlamaForCausalLM"]}')
        
        result = self.handler.verify_model('test-model')
        self.assertIsInstance(result, dict)
        self.assertIn('status', result)
        mock_validate.assert_called_once_with('test-model', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_verify_model_invalid(self, mock_validate):
        """Test verify_model with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.verify_model('../../etc/passwd')
        
        mock_validate.assert_called_once_with('../../etc/passwd', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_generate_server_config_valid(self, mock_validate):
        """Test generate_server_config with valid model name."""
        mock_validate.return_value = None
        
        config = self.handler.generate_server_config('test-model')
        self.assertIsInstance(config, dict)
        self.assertIn('model', config)
        mock_validate.assert_called_once_with('test-model', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_generate_server_config_invalid(self, mock_validate):
        """Test generate_server_config with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.generate_server_config('../../../malicious')
        
        mock_validate.assert_called_once_with('../../../malicious', provider='vllm')
    
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_export_deployment_yaml_valid(self, mock_validate, mock_open):
        """Test export_deployment_yaml with valid model name."""
        mock_validate.return_value = None
        
        result = self.handler.export_deployment_yaml('test-model', '/tmp/deployment.yaml')
        self.assertTrue(result)
        mock_validate.assert_called_once_with('test-model', provider='vllm')
    
    @patch('nvme_models.models.vllm.SecurityValidator.validate_model_id')
    def test_export_deployment_yaml_invalid(self, mock_validate):
        """Test export_deployment_yaml with invalid model name."""
        mock_validate.side_effect = ValidationError("Invalid model name")
        
        with self.assertRaises(ValidationError):
            self.handler.export_deployment_yaml('../../malicious', '/tmp/deployment.yaml')
        
        mock_validate.assert_called_once_with('../../malicious', provider='vllm')


if __name__ == '__main__':
    unittest.main()