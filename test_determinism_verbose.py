#!/usr/bin/env python3
"""
Verbose determinism test demonstrating both clients.
Shows the OpenAI SDK limitation and the workaround.
"""

import hashlib
import re
from typing import Tuple

def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    return re.sub(r'\s+', ' ', text.strip())

def test_gptoss_client() -> Tuple[bool, str]:
    """Test determinism with GPTOSSClient."""
    from src.gptoss_client import GPTOSSClient
    
    client = GPTOSSClient()
    
    # Test with deterministic settings
    prompt = "Return token: ALPHA"
    
    # First request
    txt1 = client.complete_deterministic(prompt, max_tokens=8)
    norm1 = normalize_text(txt1)
    hash1 = hashlib.md5(norm1.encode()).hexdigest()
    
    # Second request  
    txt2 = client.complete_deterministic(prompt, max_tokens=8)
    norm2 = normalize_text(txt2)
    hash2 = hashlib.md5(norm2.encode()).hexdigest()
    
    success = hash1 == hash2
    msg = f"GPTOSSClient: {'✅ PASS' if success else '❌ FAIL'}"
    if success:
        msg += f" (hash: {hash1[:8]}...)"
    else:
        msg += f"\n  Hash 1: {hash1}\n  Hash 2: {hash2}"
        msg += f"\n  Output 1: {repr(txt1)}\n  Output 2: {repr(txt2)}"
    
    return success, msg

def test_openai_client_raw() -> Tuple[bool, str]:
    """Test OpenAI client with raw request (workaround for vendor params)."""
    import requests
    import json
    
    url = "http://127.0.0.1:8010/v1/completions"
    headers = {"Content-Type": "application/json"}
    
    # Deterministic payload with vendor-specific params
    payload = {
        "model": "default",
        "prompt": "Return: BETA",
        "max_tokens": 4,
        "temperature": 0.0,
        "seed": 1337,
        "top_k": 0,  # Vendor-specific param
        "top_p": 1.0,
        "min_p": 0.0,  # Vendor-specific param
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "repeat_penalty": 1.0,  # Vendor-specific param
        "stop": ["\n\n", "###"]
    }
    
    # First request
    resp1 = requests.post(url, json=payload, headers=headers)
    txt1 = resp1.json()["choices"][0]["text"]
    norm1 = normalize_text(txt1)
    hash1 = hashlib.md5(norm1.encode()).hexdigest()
    
    # Second request
    resp2 = requests.post(url, json=payload, headers=headers)
    txt2 = resp2.json()["choices"][0]["text"]
    norm2 = normalize_text(txt2)
    hash2 = hashlib.md5(norm2.encode()).hexdigest()
    
    success = hash1 == hash2
    msg = f"OpenAI raw HTTP: {'✅ PASS' if success else '❌ FAIL'}"
    if success:
        msg += f" (hash: {hash1[:8]}...)"
    else:
        msg += f"\n  Hash 1: {hash1}\n  Hash 2: {hash2}"
        msg += f"\n  Output 1: {repr(txt1)}\n  Output 2: {repr(txt2)}"
    
    return success, msg

def main():
    print("=" * 60)
    print("DETERMINISM TEST - VERBOSE")
    print("=" * 60)
    print()
    
    # Test GPTOSSClient
    print("1. Testing GPTOSSClient (with vendor params)...")
    success1, msg1 = test_gptoss_client()
    print(f"   {msg1}")
    print()
    
    # Test OpenAI raw HTTP
    print("2. Testing raw HTTP (OpenAI-compatible with vendor params)...")
    success2, msg2 = test_openai_client_raw()
    print(f"   {msg2}")
    print()
    
    # Note about OpenAI SDK limitation
    print("NOTE: The OpenAI SDK doesn't forward vendor-specific params")
    print("      like top_k, min_p, repeat_penalty. For determinism,")
    print("      use GPTOSSClient or raw HTTP requests.")
    print()
    
    # Overall result
    print("=" * 60)
    if success1 and success2:
        print("OVERALL: ✅ All tests passed!")
    else:
        print("OVERALL: ❌ Some tests failed")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())