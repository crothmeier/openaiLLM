#!/bin/bash
set -euo pipefail

# NVMe Storage Verification Script with Enhanced Error Handling and JSON Output

# Source utility functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/nvme_checks.sh"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
OUTPUT_FORMAT="text"
while [[ $# -gt 0 ]]; do
    case $1 in
        --output=json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --help)
            echo "Usage: $0 [--output=json]"
            echo "  --output=json  Output results in JSON format for automation"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Initialize results structure
declare -A RESULTS
RESULTS["errors"]=0
RESULTS["warnings"]=0
RESULTS["success"]=0
RESULTS["messages"]=""

# Function to add result message
add_result() {
    local status=$1
    local message=$2
    local detail=${3:-""}
    
    case $status in
        "error")
            ((RESULTS["errors"]++))
            if [[ "$OUTPUT_FORMAT" == "json" ]]; then
                RESULTS["messages"]="${RESULTS["messages"]}|ERROR:$message:$detail"
            else
                echo -e "${RED}✗${NC} $message" >&2
                [[ -n "$detail" ]] && echo "  $detail" >&2
            fi
            ;;
        "warning")
            ((RESULTS["warnings"]++))
            if [[ "$OUTPUT_FORMAT" == "json" ]]; then
                RESULTS["messages"]="${RESULTS["messages"]}|WARNING:$message:$detail"
            else
                echo -e "${YELLOW}⚠${NC} $message"
                [[ -n "$detail" ]] && echo "  $detail"
            fi
            ;;
        "success")
            ((RESULTS["success"]++))
            if [[ "$OUTPUT_FORMAT" == "json" ]]; then
                RESULTS["messages"]="${RESULTS["messages"]}|SUCCESS:$message:$detail"
            else
                echo -e "${GREEN}✓${NC} $message"
                [[ -n "$detail" ]] && echo "  $detail"
            fi
            ;;
    esac
}

# Function to capture Python errors properly
run_python_check() {
    local python_output
    local python_errors
    local python_exit_code
    
    # Create temp files for capturing output
    local temp_out=$(mktemp)
    local temp_err=$(mktemp)
    
    # Run Python script and capture both stdout and stderr
    python3 - << 'PYTHON_CHECK' > "$temp_out" 2> "$temp_err"
import os
import sys
import json

results = {"transformers": None, "huggingface_hub": None}

try:
    from transformers import file_utils
    cache_dir = file_utils.default_cache_path
    if "/mnt/nvme" in cache_dir:
        results["transformers"] = {"status": "success", "path": cache_dir}
    else:
        results["transformers"] = {"status": "warning", "path": cache_dir}
except ImportError:
    results["transformers"] = {"status": "not_installed", "path": None}
except Exception as e:
    results["transformers"] = {"status": "error", "error": str(e)}

try:
    from huggingface_hub import constants
    hf_cache = constants.HF_HUB_CACHE
    if "/mnt/nvme" in hf_cache:
        results["huggingface_hub"] = {"status": "success", "path": hf_cache}
    else:
        results["huggingface_hub"] = {"status": "warning", "path": hf_cache}
except ImportError:
    results["huggingface_hub"] = {"status": "not_installed", "path": None}
except Exception as e:
    results["huggingface_hub"] = {"status": "error", "error": str(e)}

print(json.dumps(results))
PYTHON_CHECK
    
    python_exit_code=$?
    python_output=$(cat "$temp_out")
    python_errors=$(cat "$temp_err")
    
    # Clean up temp files
    rm -f "$temp_out" "$temp_err"
    
    echo "$python_output"
    return $python_exit_code
}

# Start verification
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "=== NVMe Model Storage Verification ==="
    echo ""
fi

# 1. Check NVMe mount
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "1. Checking NVMe mount point..."
fi

if mountpoint -q /mnt/nvme 2>/dev/null; then
    disk_info=$(df -h /mnt/nvme | tail -1)
    add_result "success" "/mnt/nvme is mounted" "$disk_info"
else
    add_result "error" "/mnt/nvme is not mounted!" "Run 'sudo mount /dev/nvme0n1 /mnt/nvme' or check your mount configuration"
fi

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 2. Check directory structure
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "2. Checking directory structure..."
fi

DIRS=("/mnt/nvme/hf-cache" "/mnt/nvme/models" "/mnt/nvme/ollama")
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        size=$(du -sh "$dir" 2>/dev/null | cut -f1 || echo "unknown")
        add_result "success" "$dir exists" "Size: $size"
    else
        add_result "error" "$dir does not exist" "Run setup-nvme-models.sh to create directory structure"
    fi
done

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 3. Check environment variables
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "3. Checking environment variables..."
fi

ENV_VARS=("HF_HOME" "TRANSFORMERS_CACHE" "OLLAMA_MODELS")
for var in "${ENV_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then
        add_result "success" "$var = ${!var}"
    else
        add_result "warning" "$var is not set in current shell" "Source ~/.bashrc or restart shell"
    fi
done

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 4. Check system-wide environment
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "4. Checking /etc/environment..."
fi

if [ -f /etc/environment ]; then
    if grep -q "HF_HOME" /etc/environment; then
        add_result "success" "HF_HOME configured in /etc/environment"
    else
        add_result "warning" "HF_HOME not in /etc/environment" "Run setup-nvme-models.sh with sudo"
    fi
    
    if grep -q "OLLAMA_MODELS" /etc/environment; then
        add_result "success" "OLLAMA_MODELS configured in /etc/environment"
    else
        add_result "warning" "OLLAMA_MODELS not in /etc/environment" "Run setup-nvme-models.sh with sudo"
    fi
else
    add_result "error" "/etc/environment file not found"
fi

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 5. Check for stray cache files
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "5. Checking for stray cache files..."
fi

STRAY_LOCATIONS=(
    "$HOME/.cache/huggingface"
    "$HOME/.cache/torch"
    "$HOME/.ollama"
)

for loc in "${STRAY_LOCATIONS[@]}"; do
    if [ -L "$loc" ]; then
        target=$(readlink -f "$loc" 2>/dev/null || echo "unknown")
        if [[ "$target" == /mnt/nvme/* ]]; then
            add_result "success" "$loc → $target (symlink to NVMe)"
        else
            add_result "warning" "$loc → $target (not on NVMe)"
        fi
    elif [ -d "$loc" ]; then
        size=$(du -sh "$loc" 2>/dev/null | cut -f1 || echo "0")
        if [ "$size" != "0" ] && [ "$size" != "0B" ]; then
            add_result "warning" "$loc exists with data" "Size: $size - Consider moving to NVMe"
        else
            add_result "success" "$loc exists but empty"
        fi
    else
        add_result "success" "$loc does not exist"
    fi
done

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 6. Check Python environment
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "6. Verifying Python/HF configuration..."
fi

# Check if Python is available
if command -v python3 >/dev/null 2>&1; then
    python_result=$(run_python_check 2>/dev/null || echo '{"error": "Python check failed"}')
    
    if [[ "$python_result" =~ \{.*\} ]]; then
        # Parse Python results (basic parsing without jq)
        if [[ "$python_result" == *'"transformers"'* ]]; then
            if [[ "$python_result" == *'"status": "success"'* ]] && [[ "$python_result" == *'transformers'* ]]; then
                add_result "success" "Transformers cache configured for NVMe"
            elif [[ "$python_result" == *'"status": "not_installed"'* ]] && [[ "$python_result" == *'transformers'* ]]; then
                add_result "warning" "transformers library not installed" "Install with: pip install transformers"
            else
                add_result "warning" "Transformers cache not on NVMe" "Check HF_HOME environment variable"
            fi
        fi
        
        if [[ "$python_result" == *'"huggingface_hub"'* ]]; then
            if [[ "$python_result" == *'"status": "success"'* ]] && [[ "$python_result" == *'huggingface_hub'* ]]; then
                add_result "success" "HuggingFace Hub cache configured for NVMe"
            elif [[ "$python_result" == *'"status": "not_installed"'* ]] && [[ "$python_result" == *'huggingface_hub'* ]]; then
                add_result "warning" "huggingface_hub library not installed" "Install with: pip install huggingface_hub"
            else
                add_result "warning" "HuggingFace Hub cache not on NVMe" "Check HF_HOME environment variable"
            fi
        fi
    else
        add_result "warning" "Python configuration check failed" "Python libraries may not be installed"
    fi
else
    add_result "warning" "Python3 not found" "Install Python3 to use HuggingFace models"
fi

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 7. Check disk usage
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "7. NVMe storage usage:"
    echo "------------------------"
fi

if mountpoint -q /mnt/nvme 2>/dev/null; then
    disk_usage=$(df -h /mnt/nvme | tail -1)
    available_space=$(df /mnt/nvme --output=avail -BG | tail -1 | tr -d 'G')
    
    if [[ "$OUTPUT_FORMAT" != "json" ]]; then
        echo "$disk_usage"
        echo ""
        echo "Top directories by size:"
        du -sh /mnt/nvme/* 2>/dev/null | sort -rh | head -5 || echo "No directories found"
    fi
    
    if [[ $available_space -lt 50 ]]; then
        add_result "warning" "Low disk space" "Only ${available_space}GB available"
    else
        add_result "success" "Adequate disk space" "${available_space}GB available"
    fi
else
    add_result "error" "Cannot check disk usage" "NVMe not mounted"
fi

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# 8. Check for model files
if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo "8. Model files on NVMe:"
    echo "------------------------"
fi

model_count=$(find /mnt/nvme -type f \( -name "*.safetensors" -o -name "*.bin" -o -name "*.gguf" \) 2>/dev/null | wc -l)

if [[ $model_count -gt 0 ]]; then
    add_result "success" "Found $model_count model files on NVMe"
    if [[ "$OUTPUT_FORMAT" != "json" ]]; then
        echo "Sample model files:"
        find /mnt/nvme -type f \( -name "*.safetensors" -o -name "*.bin" -o -name "*.gguf" \) 2>/dev/null | head -5
    fi
else
    add_result "warning" "No model files found yet" "Use download-models.sh to download models"
fi

if [[ "$OUTPUT_FORMAT" != "json" ]]; then
    echo ""
fi

# Output results
if [[ "$OUTPUT_FORMAT" == "json" ]]; then
    # Generate JSON output
    cat << JSON
{
  "status": $([ ${RESULTS["errors"]} -eq 0 ] && echo '"success"' || echo '"error"'),
  "errors": ${RESULTS["errors"]},
  "warnings": ${RESULTS["warnings"]},
  "success": ${RESULTS["success"]},
  "messages": [
JSON
    
    # Parse messages
    IFS='|' read -ra MESSAGES <<< "${RESULTS["messages"]}"
    first=true
    for msg in "${MESSAGES[@]}"; do
        if [[ -n "$msg" ]]; then
            IFS=':' read -r level text detail <<< "$msg"
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            echo -n "    {\"level\": \"$level\", \"message\": \"$text\""
            if [[ -n "$detail" ]]; then
                echo -n ", \"detail\": \"$detail\""
            fi
            echo -n "}"
        fi
    done
    
    cat << JSON

  ],
  "summary": {
    "nvme_mounted": $(mountpoint -q /mnt/nvme 2>/dev/null && echo "true" || echo "false"),
    "directories_created": $([ -d /mnt/nvme/hf-cache ] && [ -d /mnt/nvme/models ] && [ -d /mnt/nvme/ollama ] && echo "true" || echo "false"),
    "environment_configured": $([ -n "${HF_HOME:-}" ] && [ -n "${OLLAMA_MODELS:-}" ] && echo "true" || echo "false"),
    "model_files_found": $model_count
  }
}
JSON
else
    # Text summary
    echo "=== Summary ==="
    
    if [ ${RESULTS["errors"]} -gt 0 ]; then
        echo -e "${RED}${RESULTS["errors"]} error(s) detected. Please run setup-nvme-models.sh first.${NC}"
        exit 1
    elif [ ${RESULTS["warnings"]} -gt 0 ]; then
        echo -e "${YELLOW}Setup mostly complete. ${RESULTS["warnings"]} warning(s) detected - may need to source ~/.bashrc or restart shell.${NC}"
        exit 0
    else
        echo -e "${GREEN}All checks passed! NVMe storage is properly configured.${NC}"
        exit 0
    fi
fi