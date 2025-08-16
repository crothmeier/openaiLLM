#!/bin/bash
# Backward compatibility wrapper for setup-nvme-models.sh
# This script ensures the new Python CLI is used while maintaining the old interface

set -euo pipefail

# Check if nvme-models CLI is installed
if command -v nvme-models >/dev/null 2>&1; then
    echo "Using Python CLI for NVMe model storage setup..."
    nvme-models setup "$@"
else
    echo "Python CLI not installed. Installing nvme-models package..."
    
    # Get the directory of this script
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    # Install the package
    if [[ -f "$PROJECT_ROOT/setup.py" ]]; then
        pip install -e "$PROJECT_ROOT"
        
        # Now run the setup
        nvme-models setup "$@"
    else
        echo "Error: Could not find setup.py. Falling back to original script."
        # Fall back to original script if it exists
        if [[ -f "$SCRIPT_DIR/setup-nvme-models.sh" ]]; then
            exec "$SCRIPT_DIR/setup-nvme-models.sh" "$@"
        else
            echo "Error: Original setup script not found."
            exit 1
        fi
    fi
fi