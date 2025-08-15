"""Test cases for validators module."""

import pytest
from nvme_models.validators import SecurityValidator


class TestSecurityValidator:
    """Test cases for SecurityValidator class."""
    
    @pytest.mark.parametrize("path,expected", [
        # Valid paths
        ("models/test", True),
        ("data/file.txt", True),
        ("subfolder/nested/file.bin", True),
        ("file.txt", True),
        ("./current/dir", True),
        ("model_name-v1.0", True),
        
        # Invalid paths - directory traversal
        ("../etc/passwd", False),
        ("..\\windows\\system32", False),
        ("../../sensitive/data", False),
        ("folder/../../../etc", False),
        ("valid/path/../../../etc/passwd", False),
        
        # Invalid paths - absolute paths
        ("/etc/shadow", False),
        ("/root/.ssh/id_rsa", False),
        ("/var/log/secrets", False),
        
        # Invalid paths - Windows drive letters
        ("C:\\Windows\\System32", False),
        ("D:\\sensitive\\data", False),
        ("E:data.txt", False),
        ("Z:\\network\\share", False),
        
        # Invalid paths - UNC paths
        ("\\\\server\\share", False),
        ("\\\\192.168.1.1\\admin", False),
    ])
    def test_validate_path_traversal(self, path, expected):
        """Test path traversal validation."""
        assert SecurityValidator.validate_path_traversal(path) == expected
    
    @pytest.mark.parametrize("input_str,expected", [
        # Safe inputs
        ("simple_text", True),
        ("model-name-v1.0", True),
        ("file_name_123", True),
        ("hello world", True),
        ("data.json", True),
        ("user@example.com", True),
        ("https://example.com/path", True),
        
        # Dangerous inputs - command separators
        ("rm -rf / ;", False),
        ("test; echo hacked", False),
        ("test && malicious", False),
        ("command1 | command2", False),
        
        # Dangerous inputs - command injection
        ("test | cat /etc/passwd", False),
        ("data; rm -rf *", False),
        ("input && curl evil.com", False),
        ("$(whoami)", False),
        ("`cat /etc/shadow`", False),
        
        # Dangerous inputs - subshells and grouping
        ("(echo test)", False),
        ("{echo test}", False),
        ("test $(command)", False),
        
        # Dangerous inputs - redirection
        ("test > /etc/passwd", False),
        ("test < /etc/shadow", False),
        ("command >> sensitive.log", False),
        
        # Dangerous inputs - newlines
        ("test\nmalicious command", False),
        ("safe\r\nmalicious", False),
        ("multi\nline\ninjection", False),
        
        # Dangerous inputs - background execution
        ("command &", False),
        ("test & malicious &", False),
    ])
    def test_validate_command_injection(self, input_str, expected):
        """Test command injection validation."""
        assert SecurityValidator.validate_command_injection(input_str) == expected
    
    @pytest.mark.parametrize("name,expected", [
        # Normal names
        ("test_file.txt", "test_file.txt"),
        ("model-v1.0", "model-v1.0"),
        ("data_2024", "data_2024"),
        
        # Special characters replaced
        ("file with spaces.txt", "file_with_spaces.txt"),
        ("special!@#$%^&*()chars", "special__________chars"),
        ("path/to/file", "path_to_file"),
        ("file:with:colons", "file_with_colons"),
        ("quotes'and\"stuff", "quotes_and_stuff"),
        
        # Unicode and non-ASCII  
        ("文件名.txt", "___.txt"),
        ("naïve.txt", "na_ve.txt"),
        ("emoji😀file", "emoji_file"),
        ("Ñoño.data", "_o_o.data"),
        
        # Leading/trailing dots and spaces
        ("  .hidden.file  ", "hidden.file"),
        ("...dots...", "dots"),
        (".start_dot", "start_dot"),
        ("end_dot.", "end_dot"),
        ("   spaces   ", "spaces"),
        
        # Excessive length (>255 chars)
        ("a" * 260, "a" * 255),
        ("very_" * 60, ("very_" * 60)[:255]),
        
        # Edge cases
        ("", "unnamed"),
        (".", "unnamed"),
        ("..", "unnamed"),
        ("...", "unnamed"),
        ("   ", "unnamed"),
        ("___", "___"),
        
        # All dots/spaces
        (".....     ", "unnamed"),
        ("     .....     ", "unnamed"),
        
        # Mixed valid and invalid
        ("../../etc/passwd", "_.._etc_passwd"),
        ("/root/.ssh/id_rsa", "_root_.ssh_id_rsa"),
        ("C:\\Windows\\System32", "C__Windows_System32"),
    ])
    def test_sanitize_for_filesystem(self, name, expected):
        """Test filesystem name sanitization."""
        assert SecurityValidator.sanitize_for_filesystem(name) == expected
    
    def test_sanitize_preserves_valid_chars(self):
        """Test that sanitization preserves valid characters."""
        valid = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
        assert SecurityValidator.sanitize_for_filesystem(valid) == valid
    
    def test_sanitize_length_limit(self):
        """Test that sanitization enforces 255 character limit."""
        long_name = "a" * 300
        result = SecurityValidator.sanitize_for_filesystem(long_name)
        assert len(result) == 255
        assert result == "a" * 255
    
    def test_path_traversal_mixed_separators(self):
        """Test path traversal with mixed path separators."""
        # Mixed forward and back slashes
        assert SecurityValidator.validate_path_traversal("folder/../..\\etc") is False
        assert SecurityValidator.validate_path_traversal("..\\..//system") is False
    
    def test_command_injection_combined_attacks(self):
        """Test command injection with combined attack vectors."""
        # Multiple dangerous characters
        dangerous = "test; echo 'hacked' | cat > /tmp/pwned &"
        assert SecurityValidator.validate_command_injection(dangerous) is False
        
        # Nested command substitution
        nested = "echo $(echo `whoami`)"
        assert SecurityValidator.validate_command_injection(nested) is False
    
    def test_sanitize_idempotent(self):
        """Test that sanitization is idempotent."""
        # Running sanitize twice should give same result
        original = "test file!@# name.txt"
        once = SecurityValidator.sanitize_for_filesystem(original)
        twice = SecurityValidator.sanitize_for_filesystem(once)
        assert once == twice
    
    def test_validate_model_id(self):
        """Test model ID validation for different providers."""
        # Valid HuggingFace model IDs
        assert SecurityValidator.validate_model_id("meta-llama/Llama-2-7b", "huggingface") == (True, "")
        assert SecurityValidator.validate_model_id("microsoft/phi-2", "huggingface") == (True, "")
        assert SecurityValidator.validate_model_id("google/flan-t5-xxl", "huggingface") == (True, "")
        assert SecurityValidator.validate_model_id("stabilityai/stable-diffusion-xl-base-1.0", "huggingface") == (True, "")
        assert SecurityValidator.validate_model_id("org_name/model.name", "huggingface") == (True, "")
        assert SecurityValidator.validate_model_id("user-123/model_456", "huggingface") == (True, "")
        
        # Valid Ollama model IDs
        assert SecurityValidator.validate_model_id("llama2", "ollama") == (True, "")
        assert SecurityValidator.validate_model_id("llama2:7b", "ollama") == (True, "")
        assert SecurityValidator.validate_model_id("mistral:latest", "ollama") == (True, "")
        assert SecurityValidator.validate_model_id("codellama:13b-instruct", "ollama") == (True, "")
        assert SecurityValidator.validate_model_id("model_name", "ollama") == (True, "")
        assert SecurityValidator.validate_model_id("model-name:v1.0.0", "ollama") == (True, "")
        
        # Invalid patterns for HuggingFace
        is_valid, error = SecurityValidator.validate_model_id("just-model-name", "huggingface")
        assert is_valid is False
        assert "Invalid HuggingFace model ID format" in error
        
        is_valid, error = SecurityValidator.validate_model_id("org/model/extra", "huggingface")
        assert is_valid is False
        assert "Invalid HuggingFace model ID format" in error
        
        is_valid, error = SecurityValidator.validate_model_id("org@name/model", "huggingface")
        assert is_valid is False
        assert "Invalid HuggingFace model ID format" in error
        
        # Invalid patterns for Ollama
        is_valid, error = SecurityValidator.validate_model_id("model/name", "ollama")
        assert is_valid is False
        assert "Invalid Ollama model ID format" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model:tag:extra", "ollama")
        assert is_valid is False
        assert "Invalid Ollama model ID format" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model@name", "ollama")
        assert is_valid is False
        assert "Invalid Ollama model ID format" in error
        
        # Command injection attempts
        is_valid, error = SecurityValidator.validate_model_id("model;rm -rf /", "huggingface")
        assert is_valid is False
        assert "dangerous character" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model|cat /etc/passwd", "ollama")
        assert is_valid is False
        assert "dangerous character" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model$(whoami)", "huggingface")
        assert is_valid is False
        assert "dangerous character" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model`pwd`", "ollama")
        assert is_valid is False
        assert "dangerous character" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model&echo hacked", "huggingface")
        assert is_valid is False
        assert "dangerous character" in error
        
        # Path traversal attempts
        is_valid, error = SecurityValidator.validate_model_id("../../etc/passwd", "huggingface")
        assert is_valid is False
        assert "path traversal" in error
        
        is_valid, error = SecurityValidator.validate_model_id("../models/secret", "ollama")
        assert is_valid is False
        assert "path traversal" in error
        
        is_valid, error = SecurityValidator.validate_model_id("/etc/shadow", "huggingface")
        assert is_valid is False
        assert "path traversal" in error
        
        is_valid, error = SecurityValidator.validate_model_id("\\windows\\system32", "ollama")
        assert is_valid is False
        assert "path traversal" in error
        
        # Excessive length strings
        long_id = "a" * 257
        is_valid, error = SecurityValidator.validate_model_id(long_id, "huggingface")
        assert is_valid is False
        assert "exceeds maximum length" in error
        
        # Max valid length for HuggingFace (256 chars total)
        max_valid = "a" * 127 + "/" + "b" * 128  # 256 chars total
        assert SecurityValidator.validate_model_id(max_valid, "huggingface") == (True, "")
        
        # Max valid length for Ollama (256 chars total)
        max_valid_ollama = "a" * 128 + ":" + "b" * 127  # 256 chars total
        assert SecurityValidator.validate_model_id(max_valid_ollama, "ollama") == (True, "")
        
        # Empty model ID
        is_valid, error = SecurityValidator.validate_model_id("", "huggingface")
        assert is_valid is False
        assert "cannot be empty" in error
        
        # Unknown provider
        is_valid, error = SecurityValidator.validate_model_id("model/name", "unknown")
        assert is_valid is False
        assert "Unknown provider" in error
        
        # Case insensitive provider names
        assert SecurityValidator.validate_model_id("meta-llama/Llama-2-7b", "HuggingFace") == (True, "")
        assert SecurityValidator.validate_model_id("llama2:7b", "Ollama") == (True, "")
        assert SecurityValidator.validate_model_id("meta-llama/Llama-2-7b", "HUGGINGFACE") == (True, "")
        
        # Newline and carriage return injection
        is_valid, error = SecurityValidator.validate_model_id("model\nmalicious", "huggingface")
        assert is_valid is False
        assert "dangerous character" in error
        
        is_valid, error = SecurityValidator.validate_model_id("model\rmalicious", "ollama")
        assert is_valid is False
        assert "dangerous character" in error
        
        # Null byte injection
        is_valid, error = SecurityValidator.validate_model_id("model\x00malicious", "huggingface")
        assert is_valid is False
        assert "dangerous character" in error