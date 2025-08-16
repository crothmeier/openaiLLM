#!/bin/bash
# Backward compatibility wrapper for verify-nvme-storage.sh
# This script ensures the new Python CLI is used while maintaining the old interface

set -euo pipefail

# Parse command line arguments
OUTPUT_FORMAT="text"
for arg in "$@"; do
    case $arg in
        --output=json)
            OUTPUT_FORMAT="json"
            ;;
    esac
done

# Check if nvme-models CLI is installed
if command -v nvme-models >/dev/null 2>&1; then
    echo "Using Python CLI for NVMe storage verification..." >&2
    nvme-models verify --format "$OUTPUT_FORMAT"
else
    echo "Python CLI not installed. Installing nvme-models package..." >&2
    
    # Get the directory of this script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    # Install the package
    if [[ -f "$PROJECT_ROOT/setup.py" ]]; then
        pip install -e "$PROJECT_ROOT" >&2
        
        # Now run the verify command
        nvme-models verify --format "$OUTPUT_FORMAT"
    else
        echo "Error: Could not find setup.py. Falling back to original script." >&2
        # Fall back to original script if it exists
        if [[ -f "$SCRIPT_DIR/verify-nvme-storage.sh" ]]; then
            exec "$SCRIPT_DIR/verify-nvme-storage.sh" "$@"
        else
            echo "Error: Original verify script not found." >&2
            exit 1
        fi
    fi
fi