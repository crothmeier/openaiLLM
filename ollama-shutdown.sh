#!/bin/bash
# Graceful shutdown for daily host termination

echo "$(date): Starting graceful Ollama shutdown"

# 1. Stop accepting new requests (if you had a load balancer)
# touch /tmp/ollama.maintenance

# 2. Wait for in-flight requests (Ollama might be mid-generation)
echo "Waiting for active requests to complete..."
timeout 30 bash -c 'while curl -s http://localhost:11434/api/ps | grep -q "model"; do
  echo "  Models still active, waiting..."
  sleep 2
done'

# 3. Gracefully stop containers
echo "Stopping Docker containers..."
docker-compose -f docker-compose-ollama.yml stop -t 30

# 4. Ensure clean stop
if docker ps | grep -q ollama; then
  echo "Force stopping stuck containers..."
  docker-compose -f docker-compose-ollama.yml down
fi

# 5. Sync filesystem (paranoid but good)
sync

echo "$(date): Ollama shutdown complete"
