"""Test cases for storage module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from nvme_models.storage import NVMeStorageManager, SecurityException
from nvme_models.validators import SecurityValidator


class TestSafePathJoin:
    """Test cases for the _safe_path_join method."""
    
    @pytest.fixture
    def storage_manager(self):
        """Create a storage manager instance for testing."""
        config = {
            'storage': {
                'nvme_path': '/mnt/nvme',
                'require_mount': False,
                'min_free_space_gb': 50
            }
        }
        return NVMeStorageManager(config)
    
    def test_safe_path_join_valid_paths(self, storage_manager):
        """Test that valid paths are joined correctly."""
        # Test simple path joining
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'models')
        assert result == Path('/mnt/nvme/models')
        
        # Test multiple components
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'models', 'llama')
        assert result == Path('/mnt/nvme/models/llama')
        
        # Test with nested paths
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'hf-cache', 'models', 'bert-base')
        assert result == Path('/mnt/nvme/hf-cache/models/bert-base')
    
    def test_safe_path_join_with_path_objects(self, storage_manager):
        """Test that Path objects are handled correctly."""
        result = storage_manager._safe_path_join(Path('/mnt/nvme'), 'models')
        assert result == Path('/mnt/nvme/models')
        
        result = storage_manager._safe_path_join(storage_manager.nvme_path, Path('models'))
        assert result == Path('/mnt/nvme/models')
    
    def test_safe_path_join_rejects_traversal_attempts(self, storage_manager):
        """Test that path traversal attempts are rejected."""
        # Test parent directory traversal
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, '../etc')
        assert 'path traversal' in str(exc_info.value).lower()
        
        # Test nested traversal
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, 'models', '../../etc')
        assert 'invalid pattern' in str(exc_info.value).lower()
        
        # Test Windows-style traversal
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, '..\\windows')
        assert 'path traversal' in str(exc_info.value).lower()
    
    def test_safe_path_join_rejects_absolute_paths(self, storage_manager):
        """Test that absolute paths in components are rejected."""
        # Test Unix absolute path
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, '/etc/passwd')
        assert 'absolute path' in str(exc_info.value).lower()
        
        # Test Windows absolute path
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, 'C:\\Windows')
        assert 'invalid pattern' in str(exc_info.value).lower()
    
    def test_safe_path_join_empty_parts(self, storage_manager):
        """Test handling of empty path components."""
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join()
        assert 'No path components' in str(exc_info.value)
    
    @patch.object(SecurityValidator, 'validate_path_traversal')
    def test_safe_path_join_uses_security_validator(self, mock_validate, storage_manager):
        """Test that SecurityValidator is used for validation."""
        # Set up mock to return True for valid paths
        mock_validate.side_effect = [True, True]  # For two components (nvme_path is skipped)
        
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'models', 'test')
        
        # Verify the validator was called for each component except nvme_path
        # nvme_path is skipped because it's the base path and already validated
        assert mock_validate.call_count == 2
        assert result == Path('/mnt/nvme/models/test')
    
    @patch.object(SecurityValidator, 'validate_path_traversal')
    def test_safe_path_join_validator_rejection(self, mock_validate, storage_manager):
        """Test that validation failures from SecurityValidator are handled."""
        # Set up mock to return False for the first component after nvme_path
        mock_validate.side_effect = [False]
        
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, 'malicious_path')
        
        assert 'invalid pattern' in str(exc_info.value).lower()
        assert 'index 1' in str(exc_info.value)
    
    def test_safe_path_join_with_dots_and_slashes(self, storage_manager):
        """Test handling of various dot and slash combinations."""
        # Valid current directory reference
        result = storage_manager._safe_path_join(storage_manager.nvme_path, './models')
        assert result == Path('/mnt/nvme/./models')
        
        # Valid filename with dots
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'model.v1.0.bin')
        assert result == Path('/mnt/nvme/model.v1.0.bin')
        
        # Valid nested path
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'models/llama/7b')
        assert result == Path('/mnt/nvme/models/llama/7b')
    
    def test_safe_path_join_special_characters(self, storage_manager):
        """Test handling of special characters in path components."""
        # Valid special characters
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'model-v1_0')
        assert result == Path('/mnt/nvme/model-v1_0')
        
        result = storage_manager._safe_path_join(storage_manager.nvme_path, 'model.checkpoint')
        assert result == Path('/mnt/nvme/model.checkpoint')
    
    def test_safe_path_join_error_messages(self, storage_manager):
        """Test that error messages contain helpful information."""
        # Test error message includes the problematic component
        with pytest.raises(SecurityException) as exc_info:
            storage_manager._safe_path_join(storage_manager.nvme_path, 'valid', '../invalid')
        
        error_msg = str(exc_info.value)
        assert 'index 2' in error_msg  # Should indicate which component failed
        assert '../invalid' in error_msg  # Should show the problematic path
        assert 'path traversal' in error_msg.lower()  # Should explain the issue