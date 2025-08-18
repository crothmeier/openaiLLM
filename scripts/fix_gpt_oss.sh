#!/bin/bash
set -euo pipefail

echo "=== GPT-OSS-20B Recovery Script ==="
echo ""
echo "This script requires sudo to stop the systemd service."
echo "You will be prompted for your password."
echo ""

# Step 1: Stop and disable the auto-restarting service
echo "[1/5] Stopping systemd service..."
sudo systemctl stop llamacpp.service
sudo systemctl disable llamacpp.service

# Step 2: Kill any remaining processes
echo "[2/5] Killing existing llama-server processes..."
sudo pkill -9 -f llama-server || true
sleep 2

# Step 3: Verify GPU is clear
echo "[3/5] Checking GPU memory..."
nvidia-smi

# Step 4: Launch optimized server
echo "[4/5] Starting optimized server on port 8010..."

# Use NVMe path if available, otherwise fallback
MODEL_PATH="/mnt/nvme/models/gpt-oss-20b/gpt-oss-20b-q8_0.gguf"
TEMPLATE_PATH="/mnt/nvme/models/gpt-oss-20b/chat_template.jinja"

if [ ! -f "$MODEL_PATH" ]; then
    echo "NVMe model not found, using regular mount..."
    MODEL_PATH="/mnt/models/gpt-oss-20b/gpt-oss-20b-q8_0.gguf"
    TEMPLATE_PATH="/mnt/models/gpt-oss-20b/chat_template.jinja"
fi

echo "Model: $MODEL_PATH"
echo "Template: $TEMPLATE_PATH"

nohup /srv/llama/llama-server \
  --model "$MODEL_PATH" \
  --alias gpt-oss-20b \
  --host 127.0.0.1 \
  --port 8010 \
  --ctx-size 4096 \
  --n-gpu-layers -1 \
  --mlock \
  --chat-template "$TEMPLATE_PATH" \
  --jinja \
  --metrics \
  --log-file /tmp/llama-server.log \
  > /tmp/llama-server-stdout.log 2>&1 &

SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"

# Wait for server to be ready
echo -n "Waiting for server to be ready..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:8010/health" > /dev/null 2>&1; then
        echo " Ready!"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# Step 5: Test with corrected API call
echo "[5/5] Testing server with stop tokens..."
echo ""
echo "Test 1: Simple instruction following"
curl -s -X POST http://127.0.0.1:8010/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [
      {"role":"user", "content":"Reply with exactly five words."}
    ],
    "temperature": 0,
    "max_tokens": 16,
    "stop": ["<|end|>", "<|return|>", "<|channel|>", "<|message|>", "\n<|", "\\n<|"]
  }' | jq .

echo ""
echo "Test 2: Direct echo test"
curl -s -X POST http://127.0.0.1:8010/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-20b",
    "messages": [
      {"role":"user", "content":"Echo back: Hello World"}
    ],
    "temperature": 0,
    "max_tokens": 10,
    "stop": ["<|end|>", "<|return|>", "<|channel|>", "<|message|>", "\n<|", "\\n<|"]
  }' | jq .

echo ""
echo "=== Recovery Complete ==="
echo "Server running on: http://127.0.0.1:8010"
echo "Logs available at: /tmp/llama-server.log"
echo ""
echo "If responses are still incorrect, the model may need redownloading or"
echo "the GGUF conversion may be faulty."