"""Test cases for storage module."""

import pytest
import tempfile
import shutil
import fcntl
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock, call
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


class TestDownloadAtomic:
    """Test cases for the download_atomic method."""
    
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
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch('nvme_models.storage.shutil.move')
    @patch('nvme_models.storage.shutil.rmtree')
    @patch('nvme_models.storage.Path.mkdir')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_success(self, mock_validate_model, mock_mkdir, 
                                    mock_rmtree, mock_move, mock_mkdtemp, 
                                    storage_manager):
        """Test successful atomic download with all steps."""
        # Setup mocks
        mock_validate_model.return_value = True
        mock_mkdtemp.return_value = '/mnt/nvme/.tmp_abc_test_model'
        
        # Mock the provider handler
        with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.estimate_model_size.return_value = 5  # 5GB
            mock_handler.download_to_path.return_value = True
            mock_get_handler.return_value = mock_handler
            
            # Mock disk space check
            with patch.object(storage_manager, 'check_disk_space', return_value=True):
                # Mock validation
                with patch.object(storage_manager, '_validate_download', return_value=True):
                    # Execute
                    target_path = Path('/mnt/nvme/models/test_model')
                    result = storage_manager.download_atomic('hf', 'test/model', target_path)
                    
                    # Verify
                    assert result == target_path
                    
                    # Check tempfile.mkdtemp was called with correct parameters
                    mock_mkdtemp.assert_called_once_with(
                        prefix='.tmp_',
                        suffix='_test_model',
                        dir=Path('/mnt/nvme')
                    )
                    
                    # Check download was attempted
                    mock_handler.download_to_path.assert_called_once_with(
                        'test/model',
                        Path('/mnt/nvme/.tmp_abc_test_model/test_model')
                    )
                    
                    # Check atomic move was performed
                    mock_move.assert_called_once_with(
                        '/mnt/nvme/.tmp_abc_test_model/test_model',
                        str(target_path)
                    )
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch('nvme_models.storage.shutil.rmtree')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_cleanup_on_download_failure(self, mock_validate_model,
                                                         mock_rmtree, mock_mkdtemp,
                                                         storage_manager):
        """Test that temp directory is cleaned up when download fails."""
        # Setup mocks
        mock_validate_model.return_value = True
        temp_dir = '/mnt/nvme/.tmp_failed_download'
        mock_mkdtemp.return_value = temp_dir
        
        # Mock path exists for cleanup
        with patch('nvme_models.storage.Path.exists', return_value=True):
            # Mock the provider handler to fail download
            with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
                mock_handler = Mock()
                mock_handler.estimate_model_size.return_value = 5
                mock_handler.download_to_path.return_value = False  # Download fails
                mock_get_handler.return_value = mock_handler
                
                # Mock disk space check
                with patch.object(storage_manager, 'check_disk_space', return_value=True):
                    # Execute and expect failure
                    target_path = Path('/mnt/nvme/models/failed_model')
                    with pytest.raises(RuntimeError) as exc_info:
                        storage_manager.download_atomic('hf', 'test/model', target_path)
                    
                    assert 'Download failed' in str(exc_info.value)
                    
                    # Verify temp directory was cleaned up
                    mock_rmtree.assert_called_with(temp_dir)
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch('nvme_models.storage.shutil.rmtree')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_cleanup_on_validation_failure(self, mock_validate_model,
                                                           mock_rmtree, mock_mkdtemp,
                                                           storage_manager):
        """Test that temp directory is cleaned up when validation fails."""
        # Setup mocks
        mock_validate_model.return_value = True
        temp_dir = '/mnt/nvme/.tmp_invalid_download'
        mock_mkdtemp.return_value = temp_dir
        
        # Mock path exists for cleanup
        with patch('nvme_models.storage.Path.exists', return_value=True):
            # Mock the provider handler
            with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
                mock_handler = Mock()
                mock_handler.estimate_model_size.return_value = 5
                mock_handler.download_to_path.return_value = True  # Download succeeds
                mock_get_handler.return_value = mock_handler
                
                # Mock disk space check
                with patch.object(storage_manager, 'check_disk_space', return_value=True):
                    # Mock validation to fail
                    with patch.object(storage_manager, '_validate_download', return_value=False):
                        # Execute and expect failure
                        target_path = Path('/mnt/nvme/models/invalid_model')
                        with pytest.raises(ValueError) as exc_info:
                            storage_manager.download_atomic('hf', 'test/model', target_path)
                        
                        assert 'validation failed' in str(exc_info.value)
                        
                        # Verify temp directory was cleaned up
                        mock_rmtree.assert_called_with(temp_dir)
    
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_invalid_model_id(self, mock_validate_model, storage_manager):
        """Test that invalid model IDs are rejected."""
        # Setup mock to reject model ID
        mock_validate_model.return_value = False
        
        # Execute and expect failure
        target_path = Path('/mnt/nvme/models/malicious_model')
        with pytest.raises(SecurityException) as exc_info:
            storage_manager.download_atomic('hf', '../../../etc/passwd', target_path)
        
        assert 'Invalid model ID' in str(exc_info.value)
        
        # Verify validation was called
        mock_validate_model.assert_called_once_with('hf', '../../../etc/passwd')
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_insufficient_disk_space(self, mock_validate_model,
                                                     mock_mkdtemp, storage_manager):
        """Test that download fails gracefully when disk space is insufficient."""
        # Setup mocks
        mock_validate_model.return_value = True
        mock_mkdtemp.return_value = '/mnt/nvme/.tmp_no_space'
        
        # Mock the provider handler
        with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.estimate_model_size.return_value = 100  # 100GB required
            mock_get_handler.return_value = mock_handler
            
            # Mock disk space check to fail
            with patch.object(storage_manager, 'check_disk_space', return_value=False):
                with patch.object(storage_manager, 'get_disk_usage') as mock_usage:
                    mock_usage.return_value = {'available_gb': 10}
                    
                    # Execute and expect failure
                    target_path = Path('/mnt/nvme/models/large_model')
                    with pytest.raises(IOError) as exc_info:
                        storage_manager.download_atomic('hf', 'large/model', target_path)
                    
                    assert 'Insufficient disk space' in str(exc_info.value)
                    assert '200GB' in str(exc_info.value)  # 100GB * 2
                    assert '10GB' in str(exc_info.value)
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch('nvme_models.storage.shutil.move')
    @patch('nvme_models.storage.shutil.rmtree')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_move_failure(self, mock_validate_model, mock_rmtree,
                                          mock_move, mock_mkdtemp, storage_manager):
        """Test that temp directory is cleaned up when atomic move fails."""
        # Setup mocks
        mock_validate_model.return_value = True
        temp_dir = '/mnt/nvme/.tmp_move_fail'
        mock_mkdtemp.return_value = temp_dir
        
        # Mock move to fail
        mock_move.side_effect = OSError("Permission denied")
        
        # Mock path exists for cleanup
        with patch('nvme_models.storage.Path.exists', return_value=True):
            # Mock the provider handler
            with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
                mock_handler = Mock()
                mock_handler.estimate_model_size.return_value = 5
                mock_handler.download_to_path.return_value = True
                mock_get_handler.return_value = mock_handler
                
                # Mock disk space check
                with patch.object(storage_manager, 'check_disk_space', return_value=True):
                    # Mock validation
                    with patch.object(storage_manager, '_validate_download', return_value=True):
                        # Mock mkdir
                        with patch('nvme_models.storage.Path.mkdir'):
                            # Execute and expect failure
                            target_path = Path('/mnt/nvme/models/unmovable_model')
                            with pytest.raises(OSError) as exc_info:
                                storage_manager.download_atomic('hf', 'test/model', target_path)
                            
                            assert 'Permission denied' in str(exc_info.value)
                            
                            # Verify temp directory cleanup was attempted
                            mock_rmtree.assert_called_with(temp_dir)
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_unknown_provider(self, mock_validate_model,
                                             mock_mkdtemp, storage_manager):
        """Test that unknown providers are rejected."""
        # Setup mocks
        mock_validate_model.return_value = True
        mock_mkdtemp.return_value = '/mnt/nvme/.tmp_unknown'
        
        # Mock the provider handler to return None (unknown provider)
        with patch('nvme_models.models.get_provider_handler', return_value=None):
            # Execute and expect failure
            target_path = Path('/mnt/nvme/models/unknown_model')
            with pytest.raises(ValueError) as exc_info:
                storage_manager.download_atomic('unknown_provider', 'test/model', target_path)
            
            assert 'Unknown provider' in str(exc_info.value)
    
    def test_validate_download_nonexistent_path(self, storage_manager):
        """Test validation fails for non-existent paths."""
        # Create a mock path that doesn't exist
        with patch('nvme_models.storage.Path.exists', return_value=False):
            model_path = Path('/mnt/nvme/models/nonexistent')
            result = storage_manager._validate_download(model_path, 'hf', 'test/model')
            assert result is False
    
    def test_validate_download_hf_model_not_directory(self, storage_manager):
        """Test validation fails when HF model is not a directory."""
        model_path = Mock(spec=Path)
        model_path.exists.return_value = True
        model_path.is_dir.return_value = False
        
        result = storage_manager._validate_download(model_path, 'hf', 'test/model')
        assert result is False
    
    def test_validate_download_hf_empty_directory(self, storage_manager):
        """Test validation fails for empty HF model directory."""
        model_path = Mock(spec=Path)
        model_path.exists.return_value = True
        model_path.is_dir.return_value = True
        model_path.rglob.return_value = []  # Empty directory
        
        result = storage_manager._validate_download(model_path, 'hf', 'test/model')
        assert result is False
    
    def test_validate_download_hf_with_files(self, storage_manager):
        """Test validation passes for HF model with files."""
        model_path = Mock(spec=Path)
        model_path.exists.return_value = True
        model_path.is_dir.return_value = True
        
        # Mock some files
        mock_file1 = Mock()
        mock_file1.is_file.return_value = True
        mock_file1.stat.return_value.st_size = 1000
        mock_file1.__str__ = lambda x: '/path/model.safetensors'
        
        mock_file2 = Mock()
        mock_file2.is_file.return_value = True
        mock_file2.stat.return_value.st_size = 500
        mock_file2.__str__ = lambda x: '/path/config.json'
        
        model_path.rglob.return_value = [mock_file1, mock_file2]
        
        result = storage_manager._validate_download(model_path, 'hf', 'test/model')
        assert result is True
    
    def test_validate_download_empty_file(self, storage_manager):
        """Test validation fails for empty downloaded file."""
        model_path = Mock(spec=Path)
        model_path.exists.return_value = True
        model_path.is_file.return_value = True
        model_path.is_dir.return_value = False
        model_path.stat.return_value.st_size = 0  # Empty file
        
        result = storage_manager._validate_download(model_path, 'ollama', 'test/model')
        assert result is False
    
    def test_validate_download_non_empty_file(self, storage_manager):
        """Test validation passes for non-empty file."""
        model_path = Mock(spec=Path)
        model_path.exists.return_value = True
        model_path.is_file.return_value = True
        model_path.is_dir.return_value = False
        model_path.stat.return_value.st_size = 1000000  # Non-empty file
        
        result = storage_manager._validate_download(model_path, 'ollama', 'test/model')
        assert result is True
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    def test_download_atomic_correct_temp_dir_naming(self, mock_mkdtemp, storage_manager):
        """Test that temp directory is created with correct naming convention."""
        # Setup mocks
        with patch.object(SecurityValidator, 'validate_model_id', return_value=True):
            with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
                mock_handler = Mock()
                mock_handler.estimate_model_size.return_value = 5
                mock_handler.download_to_path.side_effect = RuntimeError("Test")
                mock_get_handler.return_value = mock_handler
                
                with patch.object(storage_manager, 'check_disk_space', return_value=True):
                    # Test with model ID containing slashes
                    target_path = Path('/mnt/nvme/models/test')
                    with pytest.raises(RuntimeError):
                        storage_manager.download_atomic('hf', 'meta-llama/Llama-2-7b', target_path)
                    
                    # Verify temp directory was created with sanitized name
                    mock_mkdtemp.assert_called_once_with(
                        prefix='.tmp_',
                        suffix='_meta-llama_Llama-2-7b',
                        dir=Path('/mnt/nvme')
                    )


class TestFileLocking:
    """Test cases for file locking mechanism in storage operations."""
    
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
    
    @patch('nvme_models.storage.fcntl.flock')
    @patch('nvme_models.storage.os.open')
    def test_acquire_lock_success(self, mock_open, mock_flock, storage_manager):
        """Test successful lock acquisition."""
        # Setup mocks
        mock_fd = 42
        mock_open.return_value = mock_fd
        mock_flock.return_value = None  # Success
        
        # Execute
        result_fd = storage_manager._acquire_lock()
        
        # Verify
        assert result_fd == mock_fd
        
        # Check lock file was opened correctly
        mock_open.assert_called_once_with(
            '/mnt/nvme/.nvme_models.lock',
            os.O_CREAT | os.O_WRONLY,
            0o644
        )
        
        # Check exclusive non-blocking lock was requested
        mock_flock.assert_called_once_with(mock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    
    @patch('nvme_models.storage.os.close')
    @patch('nvme_models.storage.fcntl.flock')
    @patch('nvme_models.storage.os.open')
    def test_acquire_lock_blocking_error(self, mock_open, mock_flock, mock_close, storage_manager):
        """Test that BlockingIOError is raised when lock is already held."""
        # Setup mocks
        mock_fd = 42
        mock_open.return_value = mock_fd
        mock_flock.side_effect = BlockingIOError("Resource temporarily unavailable")
        
        # Execute and verify exception
        with pytest.raises(BlockingIOError) as exc_info:
            storage_manager._acquire_lock()
        
        assert "another write operation is in progress" in str(exc_info.value)
        
        # Verify file descriptor was closed
        mock_close.assert_called_once_with(mock_fd)
    
    @patch('nvme_models.storage.os.close')
    @patch('nvme_models.storage.fcntl.flock')
    @patch('nvme_models.storage.os.open')
    def test_acquire_lock_general_error(self, mock_open, mock_flock, mock_close, storage_manager):
        """Test that IOError is raised for general lock failures."""
        # Setup mocks
        mock_fd = 42
        mock_open.return_value = mock_fd
        mock_flock.side_effect = OSError("Permission denied")
        
        # Execute and verify exception
        with pytest.raises(IOError) as exc_info:
            storage_manager._acquire_lock()
        
        assert "Failed to acquire lock" in str(exc_info.value)
        
        # Verify file descriptor was closed
        mock_close.assert_called_once_with(mock_fd)
    
    @patch('nvme_models.storage.os.close')
    @patch('nvme_models.storage.fcntl.flock')
    def test_release_lock_success(self, mock_flock, mock_close, storage_manager):
        """Test successful lock release."""
        # Setup
        mock_fd = 42
        
        # Execute
        storage_manager._release_lock(mock_fd)
        
        # Verify
        mock_flock.assert_called_once_with(mock_fd, fcntl.LOCK_UN)
        mock_close.assert_called_once_with(mock_fd)
    
    @patch('nvme_models.storage.os.close')
    @patch('nvme_models.storage.fcntl.flock')
    def test_release_lock_with_error_still_closes_fd(self, mock_flock, mock_close, storage_manager):
        """Test that file descriptor is closed even if unlock fails."""
        # Setup
        mock_fd = 42
        mock_flock.side_effect = OSError("Failed to unlock")
        
        # Execute (should not raise)
        storage_manager._release_lock(mock_fd)
        
        # Verify close was still attempted
        mock_close.assert_called_once_with(mock_fd)
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch('nvme_models.storage.shutil.move')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_with_lock_acquisition_and_release(self, mock_validate_model,
                                                               mock_move, mock_mkdtemp,
                                                               storage_manager):
        """Test that lock is acquired at start and released in finally block."""
        # Setup mocks
        mock_validate_model.return_value = True
        mock_mkdtemp.return_value = '/mnt/nvme/.tmp_test'
        mock_lock_fd = 42
        
        with patch.object(storage_manager, '_acquire_lock', return_value=mock_lock_fd) as mock_acquire:
            with patch.object(storage_manager, '_release_lock') as mock_release:
                with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
                    mock_handler = Mock()
                    mock_handler.estimate_model_size.return_value = 5
                    mock_handler.download_to_path.return_value = True
                    mock_get_handler.return_value = mock_handler
                    
                    with patch.object(storage_manager, 'check_disk_space', return_value=True):
                        with patch.object(storage_manager, '_validate_download', return_value=True):
                            with patch('nvme_models.storage.Path.mkdir'):
                                with patch('nvme_models.storage.Path.exists', return_value=False):
                                    # Execute
                                    target_path = Path('/mnt/nvme/models/test')
                                    result = storage_manager.download_atomic('hf', 'test/model', target_path)
                                    
                                    # Verify lock was acquired
                                    mock_acquire.assert_called_once()
                                    
                                    # Verify lock was released
                                    mock_release.assert_called_once_with(mock_lock_fd)
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_releases_lock_on_exception(self, mock_validate_model,
                                                        mock_mkdtemp, storage_manager):
        """Test that lock is always released in finally block even on exception."""
        # Setup mocks
        mock_validate_model.return_value = True
        mock_mkdtemp.return_value = '/mnt/nvme/.tmp_failed'
        mock_lock_fd = 42
        
        with patch.object(storage_manager, '_acquire_lock', return_value=mock_lock_fd) as mock_acquire:
            with patch.object(storage_manager, '_release_lock') as mock_release:
                with patch('nvme_models.models.get_provider_handler') as mock_get_handler:
                    # Make download fail
                    mock_handler = Mock()
                    mock_handler.estimate_model_size.return_value = 5
                    mock_handler.download_to_path.side_effect = RuntimeError("Download failed")
                    mock_get_handler.return_value = mock_handler
                    
                    with patch.object(storage_manager, 'check_disk_space', return_value=True):
                        with patch('nvme_models.storage.Path.exists', return_value=True):
                            with patch('nvme_models.storage.shutil.rmtree'):
                                # Execute and expect failure
                                target_path = Path('/mnt/nvme/models/test')
                                with pytest.raises(RuntimeError):
                                    storage_manager.download_atomic('hf', 'test/model', target_path)
                                
                                # Verify lock was acquired
                                mock_acquire.assert_called_once()
                                
                                # Verify lock was still released despite exception
                                mock_release.assert_called_once_with(mock_lock_fd)
    
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_concurrent_lock_failure(self, mock_validate_model, storage_manager):
        """Test that concurrent download attempts fail with BlockingIOError."""
        # Setup mocks
        mock_validate_model.return_value = True
        
        # Make lock acquisition fail with BlockingIOError
        with patch.object(storage_manager, '_acquire_lock') as mock_acquire:
            mock_acquire.side_effect = BlockingIOError("Cannot acquire lock - another write operation is in progress")
            
            # Execute and expect BlockingIOError
            target_path = Path('/mnt/nvme/models/test')
            with pytest.raises(BlockingIOError) as exc_info:
                storage_manager.download_atomic('hf', 'test/model', target_path)
            
            assert "another write operation is in progress" in str(exc_info.value)
            
            # Verify lock acquisition was attempted
            mock_acquire.assert_called_once()
    
    @patch('nvme_models.storage.tempfile.mkdtemp')
    @patch.object(SecurityValidator, 'validate_model_id')
    def test_download_atomic_no_lock_release_if_not_acquired(self, mock_validate_model,
                                                             mock_mkdtemp, storage_manager):
        """Test that lock release is not attempted if lock was never acquired."""
        # Setup mocks
        mock_validate_model.return_value = True
        
        # Make lock acquisition fail immediately
        with patch.object(storage_manager, '_acquire_lock') as mock_acquire:
            mock_acquire.side_effect = IOError("Cannot create lock file")
            
            with patch.object(storage_manager, '_release_lock') as mock_release:
                # Execute and expect failure
                target_path = Path('/mnt/nvme/models/test')
                with pytest.raises(IOError):
                    storage_manager.download_atomic('hf', 'test/model', target_path)
                
                # Verify lock release was NOT called (since lock_fd would be None)
                mock_release.assert_not_called()
    
    @patch('nvme_models.storage.os.open')
    def test_acquire_lock_creates_lock_file(self, mock_open, storage_manager, tmp_path):
        """Test that lock file is created with correct permissions."""
        # Use a real temp directory for this test
        storage_manager.nvme_path = tmp_path
        lock_file_path = tmp_path / '.nvme_models.lock'
        
        # Setup mock to simulate successful lock
        mock_fd = 42
        mock_open.return_value = mock_fd
        
        with patch('nvme_models.storage.fcntl.flock'):
            # Execute
            result_fd = storage_manager._acquire_lock()
            
            # Verify open was called with correct parameters
            mock_open.assert_called_once_with(
                str(lock_file_path),
                os.O_CREAT | os.O_WRONLY,
                0o644
            )
            
            assert result_fd == mock_fd