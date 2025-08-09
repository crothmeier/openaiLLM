#!/bin/bash
# Security validation module for model storage scripts
# Provides functions for input validation and path sanitization

set -euo pipefail

# POSIX-safe function to validate model ID - rejects traversal and unsafe chars
# Returns 0 if valid, 1 if invalid (exits with nonzero on violation)
validate_model_id() {
    local model_id="$1"
    
    # Check if model_id is empty
    if [[ -z "$model_id" ]]; then
        echo "ERROR: Model ID cannot be empty" >&2
        return 1
    fi
    
    # Check for path traversal attempts
    case "$model_id" in
        *..*)
            echo "ERROR: Model ID contains path traversal sequence (..)" >&2
            return 1
            ;;
        */*)
            # Allow forward slashes for organization/model format
            # But check for double slashes and leading/trailing slashes
            case "$model_id" in
                //*|*//|/*|*/)
                    echo "ERROR: Model ID contains invalid slash patterns" >&2
                    return 1
                    ;;
            esac
            ;;
    esac
    
    # Check for unsafe characters using POSIX character classes
    # Allow only alphanumeric, dash, underscore, dot, and single forward slash
    if ! echo "$model_id" | grep -qE '^[A-Za-z0-9._/-]+$'; then
        echo "ERROR: Model ID contains unsafe characters" >&2
        echo "       Allowed: alphanumeric, dash, underscore, dot, forward slash" >&2
        return 1
    fi
    
    # Check for special shell characters that could cause issues
    case "$model_id" in
        *[\;\|\&\<\>\$\`\(\)\{\}\[\]\*\?\~\!\#\%\^\=\+\\\'\"]*)
            echo "ERROR: Model ID contains shell special characters" >&2
            return 1
            ;;
    esac
    
    # Additional check for hidden files/directories
    case "$model_id" in
        .*|*/.*)
            echo "ERROR: Model ID cannot reference hidden files or directories" >&2
            return 1
            ;;
    esac
    
    # Check maximum length (reasonable limit)
    if [[ ${#model_id} -gt 256 ]]; then
        echo "ERROR: Model ID exceeds maximum length of 256 characters" >&2
        return 1
    fi
    
    # If all checks pass
    return 0
}

# Validate and sanitize file paths to prevent path traversal
validate_path() {
    local path="$1"
    local base_dir="${2:-/mnt/nvme}"  # Default base directory
    
    # Check for empty input
    if [[ -z "$path" ]]; then
        echo "Error: Empty path provided" >&2
        return 1
    fi
    
    # Check for path traversal attempts
    if echo "$path" | grep -qE '(^|/)\.\.(/|$)|^~'; then
        echo "Error: Path traversal attempt detected in: $path" >&2
        return 1
    fi
    
    # Resolve to absolute path and check if within boundary
    local abs_path
    abs_path=$(realpath -m "$path" 2>/dev/null) || {
        echo "Error: Invalid path: $path" >&2
        return 1
    }
    
    # Ensure path is within allowed boundary
    if [[ ! "$abs_path" =~ ^"$base_dir" ]]; then
        echo "Error: Path outside allowed boundary: $abs_path" >&2
        echo "  Must be within: $base_dir" >&2
        return 1
    fi
    
    echo "$abs_path"
    return 0
}

# Sanitize strings for safe filesystem operations
sanitize_string() {
    local input="$1"
    local allow_slash="${2:-false}"
    
    # Remove null bytes and control characters
    local sanitized
    sanitized=$(echo "$input" | tr -d '\000-\037')
    
    if [[ "$allow_slash" == "false" ]]; then
        # Remove slashes and other dangerous characters
        sanitized=$(echo "$sanitized" | sed 's/[^a-zA-Z0-9._-]/-/g')
    else
        # Keep slashes but remove other dangerous characters
        sanitized=$(echo "$sanitized" | sed 's/[^a-zA-Z0-9._/-]/-/g')
    fi
    
    # Remove consecutive dots and slashes
    sanitized=$(echo "$sanitized" | sed 's/\.\.//g' | sed 's|//|/|g')
    
    # Trim leading/trailing dots and slashes
    sanitized=$(echo "$sanitized" | sed 's/^[./]*//;s/[./]*$//')
    
    echo "$sanitized"
}

# Validate HuggingFace model ID format
validate_hf_model_id() {
    local model_id="$1"
    
    # Check format: owner/model-name
    if ! echo "$model_id" | grep -qE '^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$'; then
        echo "Error: Invalid HuggingFace model ID format: $model_id" >&2
        echo "  Expected format: owner/model-name" >&2
        return 1
    fi
    
    # Additional safety checks
    if echo "$model_id" | grep -qE '(\.\.|//|^/|/$|^\.|\.$)'; then
        echo "Error: Suspicious pattern in model ID: $model_id" >&2
        return 1
    fi
    
    return 0
}

# Validate Ollama model name format
validate_ollama_model() {
    local model="$1"
    
    # Check format: model:tag or just model
    if ! echo "$model" | grep -qE '^[a-zA-Z0-9_-]+(:[a-zA-Z0-9._-]+)?$'; then
        echo "Error: Invalid Ollama model format: $model" >&2
        echo "  Expected format: model or model:tag" >&2
        return 1
    fi
    
    return 0
}

# Check file ownership before sensitive operations
check_file_ownership() {
    local file="$1"
    local expected_user="${2:-$(whoami)}"
    
    if [[ ! -e "$file" ]]; then
        echo "Error: File does not exist: $file" >&2
        return 1
    fi
    
    local file_owner
    file_owner=$(stat -c '%U' "$file" 2>/dev/null) || {
        echo "Error: Cannot determine ownership of: $file" >&2
        return 1
    }
    
    if [[ "$file_owner" != "$expected_user" ]]; then
        echo "Error: File ownership mismatch for: $file" >&2
        echo "  Expected: $expected_user, Found: $file_owner" >&2
        return 1
    fi
    
    return 0
}

# Validate directory for write operations
validate_write_directory() {
    local dir="$1"
    
    # First validate the path
    local safe_dir
    safe_dir=$(validate_path "$dir") || return 1
    
    # Check if directory exists and is writable
    if [[ ! -d "$safe_dir" ]]; then
        echo "Error: Directory does not exist: $safe_dir" >&2
        return 1
    fi
    
    if [[ ! -w "$safe_dir" ]]; then
        echo "Error: Directory is not writable: $safe_dir" >&2
        return 1
    fi
    
    echo "$safe_dir"
    return 0
}

# Validate environment variables
validate_env_vars() {
    local required_vars=("HF_HOME" "TRANSFORMERS_CACHE" "OLLAMA_MODELS")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo "Error: Required environment variables not set:" >&2
        printf "  %s\n" "${missing_vars[@]}" >&2
        return 1
    fi
    
    # Validate paths in environment variables
    for var in "${required_vars[@]}"; do
        local path="${!var}"
        validate_path "$path" >/dev/null || {
            echo "Error: Invalid path in $var: $path" >&2
            return 1
        }
    done
    
    return 0
}

# Safe command execution with timeout
safe_exec() {
    local timeout="${1:-30}"
    shift
    local command=("$@")
    
    # Validate command doesn't contain shell metacharacters
    for arg in "${command[@]}"; do
        if echo "$arg" | grep -qE '[;&|<>$`\\]'; then
            echo "Error: Potentially dangerous characters in command argument: $arg" >&2
            return 1
        fi
    done
    
    # Execute with timeout
    timeout "$timeout" "${command[@]}"
}

# Log security events
log_security_event() {
    local event_type="$1"
    local message="$2"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    echo "[SECURITY] [$timestamp] [$event_type] $message" >&2
    
    # Also log to syslog if available
    if command -v logger >/dev/null 2>&1; then
        logger -t "model-security" -p user.warning "[$event_type] $message"
    fi
}

# Export functions for use by other scripts
export -f validate_model_id
export -f validate_path
export -f sanitize_string
export -f validate_hf_model_id
export -f validate_ollama_model
export -f check_file_ownership
export -f validate_write_directory
export -f validate_env_vars
export -f safe_exec
export -f log_security_event