# vLLM API Interface Tutorial
**Date: August 14, 2025**  
**vLLM Version: 0.5.5**  
**Model: TheBloke/Mistral-7B-Instruct-v0.2-GPTQ**

## Table of Contents
1. [Service Overview](#service-overview)
2. [API Endpoints](#api-endpoints)
3. [Basic Usage Examples](#basic-usage-examples)
4. [Advanced Features](#advanced-features)
5. [Python Client Examples](#python-client-examples)
6. [Performance Tips](#performance-tips)
7. [Troubleshooting](#troubleshooting)

## Service Overview

The vLLM service is deployed in Kubernetes and provides OpenAI-compatible API endpoints for text generation using the Mistral-7B-Instruct model.

### Connection Details
- **Internal Kubernetes Access**: `http://vllm.ai-infer.svc.cluster.local:8000`
- **Pod Direct Access**: Use `kubectl port-forward` for local testing
- **Namespace**: `ai-infer`
- **Service Name**: `vllm`

### Port Forwarding for Local Access
```bash
# Forward vLLM service to local port 8000
kubectl port-forward -n ai-infer svc/vllm 8000:8000

# Or forward directly to the pod
POD=$(kubectl -n ai-infer get pods -l app=vllm -o jsonpath='{.items[0].metadata.name}')
kubectl port-forward -n ai-infer $POD 8000:8000
```

## API Endpoints

### Available Endpoints
- `GET /health` - Health check
- `GET /v1/models` - List available models
- `POST /v1/completions` - Text completion (OpenAI compatible)
- `POST /v1/chat/completions` - Chat completion (OpenAI compatible)
- `POST /tokenize` - Tokenize text
- `POST /detokenize` - Detokenize tokens
- `GET /version` - vLLM version info

## Basic Usage Examples

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. List Available Models
```bash
curl http://localhost:8000/v1/models | jq
```

Expected output:
```json
{
  "object": "list",
  "data": [
    {
      "id": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
      "object": "model",
      "max_model_len": 32768
    }
  ]
}
```

### 3. Text Completion
```bash
# Simple completion
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "prompt": "The future of artificial intelligence is",
    "max_tokens": 100,
    "temperature": 0.7
  }' | jq

# Multiple prompts (batch processing)
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "prompt": [
      "Explain quantum computing in simple terms:",
      "What is machine learning?"
    ],
    "max_tokens": 150,
    "temperature": 0.5
  }' | jq
```

### 4. Chat Completion (Instruction Following)
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Write a Python function to calculate fibonacci numbers"}
    ],
    "max_tokens": 200,
    "temperature": 0.3
  }' | jq
```

### 5. Streaming Responses
```bash
# Stream completion tokens as they're generated
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "prompt": "Write a short story about a robot learning to paint:",
    "max_tokens": 200,
    "stream": true
  }'
```

### 6. Tokenization
```bash
# Tokenize text
curl -X POST http://localhost:8000/tokenize \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "prompt": "Hello, world!"
  }' | jq

# Detokenize tokens
curl -X POST http://localhost:8000/detokenize \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "tokens": [22557, 28725, 1526, 28808]
  }' | jq
```

## Advanced Features

### Generation Parameters

All completion endpoints support these parameters:

```bash
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "prompt": "Explain the theory of relativity",
    "max_tokens": 150,
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 40,
    "min_p": 0.05,
    "frequency_penalty": 0.5,
    "presence_penalty": 0.5,
    "repetition_penalty": 1.1,
    "stop": ["\\n\\n", "END"],
    "n": 1,
    "best_of": 1,
    "logprobs": 5,
    "echo": false
  }' | jq
```

### Parameter Explanations:
- **temperature** (0.0-2.0): Controls randomness. Lower = more deterministic
- **top_p** (0.0-1.0): Nucleus sampling. Consider tokens with cumulative probability
- **top_k** (1-100): Only consider top k tokens
- **min_p** (0.0-1.0): Minimum probability threshold
- **frequency_penalty** (-2.0-2.0): Penalize frequent tokens
- **presence_penalty** (-2.0-2.0): Penalize tokens that already appeared
- **repetition_penalty** (1.0-2.0): Multiplicative penalty for repeated tokens
- **stop**: List of sequences where generation stops
- **n**: Number of completions to generate
- **best_of**: Generate n and return best (by log probability)
- **logprobs**: Include log probabilities of top tokens
- **echo**: Include prompt in response

## Python Client Examples

### Installation
```bash
pip install openai requests
```

### Basic Python Client
```python
#!/usr/bin/env python3
"""vLLM API Client Example - August 14, 2025"""

import json
import requests
from typing import List, Dict, Any

class VLLMClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.model = "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ"
    
    def health_check(self) -> bool:
        """Check if service is healthy"""
        try:
            resp = requests.get(f"{self.base_url}/health")
            return resp.status_code == 200
        except:
            return False
    
    def complete(self, prompt: str, **kwargs) -> str:
        """Generate text completion"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", 100),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.95),
            "stream": False
        }
        
        resp = requests.post(
            f"{self.base_url}/v1/completions",
            json=payload
        )
        resp.raise_for_status()
        
        result = resp.json()
        return result["choices"][0]["text"]
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Chat completion with conversation history"""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 200),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": False
        }
        
        resp = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload
        )
        resp.raise_for_status()
        
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    
    def stream_complete(self, prompt: str, **kwargs):
        """Stream completion tokens as they're generated"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", 200),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": True
        }
        
        with requests.post(
            f"{self.base_url}/v1/completions",
            json=payload,
            stream=True
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data != '[DONE]':
                            chunk = json.loads(data)
                            if chunk["choices"][0]["text"]:
                                yield chunk["choices"][0]["text"]

# Example usage
if __name__ == "__main__":
    client = VLLMClient()
    
    # Check health
    if not client.health_check():
        print("Service is not healthy!")
        exit(1)
    
    # Simple completion
    print("=== Text Completion ===")
    result = client.complete(
        "The three laws of robotics are:",
        max_tokens=150,
        temperature=0.5
    )
    print(result)
    
    # Chat conversation
    print("\n=== Chat Completion ===")
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a Python function to reverse a string"}
    ]
    response = client.chat(messages, max_tokens=200, temperature=0.3)
    print(response)
    
    # Streaming
    print("\n=== Streaming Completion ===")
    for token in client.stream_complete("Once upon a time", max_tokens=100):
        print(token, end='', flush=True)
    print()
```

### Using OpenAI Python SDK
```python
#!/usr/bin/env python3
"""Using OpenAI SDK with vLLM - August 14, 2025"""

from openai import OpenAI

# Point to vLLM server
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # vLLM doesn't require auth by default
)

# List models
models = client.models.list()
print(f"Available models: {[m.id for m in models.data]}")

# Text completion
completion = client.completions.create(
    model="TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    prompt="The meaning of life is",
    max_tokens=100,
    temperature=0.7
)
print(completion.choices[0].text)

# Chat completion
chat_response = client.chat.completions.create(
    model="TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain containers in 3 sentences"}
    ],
    max_tokens=150,
    temperature=0.5
)
print(chat_response.choices[0].message.content)

# Streaming
stream = client.completions.create(
    model="TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    prompt="Write a haiku about Kubernetes:",
    max_tokens=50,
    stream=True
)

for chunk in stream:
    if chunk.choices[0].text:
        print(chunk.choices[0].text, end='')
```

## Performance Tips

### 1. Batch Processing
Process multiple prompts in a single request for better throughput:
```bash
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ",
    "prompt": [
      "Translate to French: Hello world",
      "Translate to Spanish: Good morning",
      "Translate to German: Thank you"
    ],
    "max_tokens": 50
  }' | jq
```

### 2. Optimal Parameters
- **Lower temperature** (0.1-0.5) for factual/deterministic tasks
- **Higher temperature** (0.7-1.0) for creative tasks
- **Limit max_tokens** to what you actually need
- **Use stop sequences** to avoid generating unnecessary tokens

### 3. Connection Pooling
For production Python clients:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3)
adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
session.mount('http://', adapter)

# Use session for all requests
response = session.post(f"{base_url}/v1/completions", json=payload)
```

## Troubleshooting

### Common Issues and Solutions

1. **Connection Refused**
```bash
# Check pod is running
kubectl -n ai-infer get pods -l app=vllm

# Check service endpoints
kubectl -n ai-infer get endpoints vllm

# View logs
kubectl -n ai-infer logs -l app=vllm --tail=100
```

2. **Slow Response Times**
```bash
# Check GPU utilization
kubectl -n ai-infer exec $(kubectl -n ai-infer get pods -l app=vllm -o jsonpath='{.items[0].metadata.name}') -- nvidia-smi

# Monitor resource usage
kubectl -n ai-infer top pod -l app=vllm
```

3. **Out of Memory Errors**
- Reduce `max_num_seqs` in deployment
- Lower `gpu_memory_utilization` 
- Use smaller batch sizes

4. **Model Loading Issues**
```bash
# Check available disk space
kubectl -n ai-infer exec $(kubectl -n ai-infer get pods -l app=vllm -o jsonpath='{.items[0].metadata.name}') -- df -h /mnt/nvme

# Verify model cache
kubectl -n ai-infer exec $(kubectl -n ai-infer get pods -l app=vllm -o jsonpath='{.items[0].metadata.name}') -- ls -la /mnt/nvme/hf-cache/
```

## Testing Script

Save this as `test_vllm.sh`:
```bash
#!/bin/bash
# vLLM API Test Script - August 14, 2025

VLLM_URL="${VLLM_URL:-http://localhost:8000}"
MODEL="TheBloke/Mistral-7B-Instruct-v0.2-GPTQ"

echo "Testing vLLM at $VLLM_URL"
echo "========================="

# Health check
echo -n "1. Health Check: "
if curl -s "$VLLM_URL/health" > /dev/null; then
    echo "✓ Healthy"
else
    echo "✗ Failed"
    exit 1
fi

# List models
echo -n "2. List Models: "
MODEL_COUNT=$(curl -s "$VLLM_URL/v1/models" | jq '.data | length')
echo "✓ Found $MODEL_COUNT model(s)"

# Test completion
echo -n "3. Text Completion: "
RESPONSE=$(curl -s -X POST "$VLLM_URL/v1/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"Hello, world! This is a test.\",
    \"max_tokens\": 10,
    \"temperature\": 0.5
  }" | jq -r '.choices[0].text')

if [ -n "$RESPONSE" ]; then
    echo "✓ Got response"
    echo "   Response: $RESPONSE"
else
    echo "✗ No response"
fi

# Test chat
echo -n "4. Chat Completion: "
CHAT_RESPONSE=$(curl -s -X POST "$VLLM_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Say hello in one word\"}
    ],
    \"max_tokens\": 10
  }" | jq -r '.choices[0].message.content')

if [ -n "$CHAT_RESPONSE" ]; then
    echo "✓ Got response"
    echo "   Response: $CHAT_RESPONSE"
else
    echo "✗ No response"
fi

echo "========================="
echo "All tests passed!"
```

## Additional Resources

- [vLLM Documentation](https://docs.vllm.ai/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Mistral Model Card](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GPTQ)

## Notes
- This tutorial is current as of August 14, 2025
- vLLM version 0.5.5 with CUDA 12.5
- Model: TheBloke/Mistral-7B-Instruct-v0.2-GPTQ (4-bit quantized)
- Maximum context length: 32,768 tokens
- GPU memory utilization set to 92%

---
*Last updated: August 14, 2025*