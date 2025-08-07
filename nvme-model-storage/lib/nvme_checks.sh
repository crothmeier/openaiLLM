#!/bin/bash

die() {
    echo "ERROR: $1" >&2
    exit 1
}

check_nvme_mounted() {
    mountpoint -q /mnt/nvme || die "NVMe not mounted"
}

check_disk_space() {
    local required_gb=$1
    local available=$(df /mnt/nvme --output=avail -BG | tail -1 | tr -d 'G')
    [[ $available -lt $required_gb ]] && die "Insufficient space on NVMe (available: ${available}GB, required: ${required_gb}GB)"
}

acquire_lock() {
    exec 200>/var/lock/nvme-models.lock
    flock -n 200 || die "Another operation is already in progress"
}

release_lock() {
    exec 200>&-
}

estimate_model_size() {
    local model_id=$1
    echo "Estimating size for model: $model_id" >&2
    
    # Try to get model info via Hugging Face API
    local api_url="https://huggingface.co/api/models/${model_id}"
    local response=$(curl -s -f "$api_url" 2>/dev/null)
    
    if [[ $? -eq 0 ]] && [[ -n "$response" ]]; then
        # Try to extract safetensors size from siblings array
        local size_bytes=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    total_size = 0
    if 'siblings' in data:
        for file in data['siblings']:
            if 'size' in file:
                total_size += file['size']
    if total_size > 0:
        print(total_size)
    else:
        print(0)
except:
    print(0)
" 2>/dev/null)
        
        if [[ "$size_bytes" =~ ^[0-9]+$ ]] && [[ "$size_bytes" -gt 0 ]]; then
            # Convert bytes to GB (rounded up)
            local size_gb=$(( (size_bytes + 1073741823) / 1073741824 ))
            echo "$size_gb"
            return 0
        fi
    fi
    
    # Fallback: estimate based on common model sizes
    case "$model_id" in
        *7b*|*7B*)
            echo "15"  # 7B models typically need ~15GB
            ;;
        *13b*|*13B*)
            echo "30"  # 13B models typically need ~30GB
            ;;
        *30b*|*30B*|*33b*|*33B*)
            echo "65"  # 30-33B models typically need ~65GB
            ;;
        *70b*|*70B*)
            echo "140"  # 70B models typically need ~140GB
            ;;
        *)
            echo "50"  # Default conservative estimate
            ;;
    esac
}

verify_python() {
    command -v python3 >/dev/null 2>&1 || die "Python3 is required but not installed"
}

verify_huggingface_cli() {
    command -v huggingface-cli >/dev/null 2>&1 || die "huggingface-cli is required but not installed"
}

backup_file() {
    local file=$1
    local backup="${file}.bak.$(date +%s)"
    cp "$file" "$backup" 2>/dev/null || die "Failed to backup $file"
    echo "$backup"
}

restore_file() {
    local backup=$1
    local original=${backup%.bak.*}
    if [[ -f "$backup" ]]; then
        mv "$backup" "$original" || die "Failed to restore $original from $backup"
    fi
}

cleanup_old_backups() {
    local file=$1
    local keep_days=${2:-7}
    find "$(dirname "$file")" -name "$(basename "$file").bak.*" -mtime +$keep_days -delete 2>/dev/null
}