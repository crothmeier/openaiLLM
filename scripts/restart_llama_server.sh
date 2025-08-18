#!/bin/bash
set -euo pipefail

# Restart llama.cpp server with determinism flags

# Configuration
MODEL_PATH="${MODEL_PATH:-/mnt/models/gpt-oss-20b/model.gguf}"
LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_PORT:-8010}"
N_GPU_LAYERS="${N_GPU_LAYERS:-999}"
CTX_SIZE="${CTX_SIZE:-4096}"
THREADS="${THREADS:-8}"
SEED="${SEED:-1337}"

# Respect DETERMINISM=1 to disable cont-batching for test lane
if [ "${DETERMINISM:-0}" = "1" ]; then
    echo "Running in DETERMINISM mode (no cont-batching, fixed seed)"
    CONT_BATCHING=""
else
    echo "Running in normal mode (with cont-batching)"
    CONT_BATCHING="--cont-batching"
fi

# Check if server is running and stop it
echo "Checking for existing llama-server process..."
if pgrep -f "llama-server.*--port.*${LLAMA_PORT}" > /dev/null; then
    echo "Stopping existing server..."
    pkill -f "llama-server.*--port.*${LLAMA_PORT}" || true
    sleep 2
fi

# Ensure the model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model not found at $MODEL_PATH"
    exit 1
fi

# Start the server
echo "Starting llama-server on ${LLAMA_HOST}:${LLAMA_PORT}..."
echo "Model: $MODEL_PATH"
echo "GPU Layers: $N_GPU_LAYERS"
echo "Context: $CTX_SIZE"
echo "Threads: $THREADS"
echo "Seed: $SEED"

nohup /srv/llama/llama-server \
    --no-webui \
    --model "$MODEL_PATH" \
    --host "$LLAMA_HOST" \
    --port "$LLAMA_PORT" \
    --alias gpt-oss-20b \
    --mlock \
    --n-gpu-layers "$N_GPU_LAYERS" \
    --ctx-size "$CTX_SIZE" \
    --threads "$THREADS" \
    --seed "$SEED" \
    $CONT_BATCHING \
    --metrics \
    > /tmp/llama-server.log 2>&1 &

SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"

# Wait for server to be ready
echo -n "Waiting for server to be ready..."
for i in {1..30}; do
    if curl -s "http://${LLAMA_HOST}:${LLAMA_PORT}/health" > /dev/null 2>&1; then
        echo " Ready!"
        echo "Server is running at http://${LLAMA_HOST}:${LLAMA_PORT}"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo " Failed!"
echo "Server failed to start. Check /tmp/llama-server.log for details:"
tail -20 /tmp/llama-server.log
exit 1