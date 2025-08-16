#!/bin/bash
# Morning startup routine

echo "$(date): Starting Ollama infrastructure"

# 1. Verify NVMe is mounted
if ! mountpoint -q /mnt/nvme; then
  echo "ERROR: /mnt/nvme not mounted!"
  exit 1
fi

# 2. Start containers
docker-compose -f docker-compose-ollama.yml up -d

# 3. Wait for health
echo "Waiting for Ollama to be ready..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
  echo "  Waiting for Ollama API..."
  sleep 2
done

# 4. Warm up a model (optional, preloads into memory)
# docker exec ollama-nvme ollama run llama2:7b "test" > /dev/null 2>&1

echo "$(date): Ollama ready for existential investigations"
