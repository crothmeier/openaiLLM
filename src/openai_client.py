#!/usr/bin/env python3
"""OpenAI-compatible client for llama.cpp endpoint."""

import sys
import time
import json
from typing import Optional
from openai import OpenAI


def complete(
    prompt: str,
    max_tokens: int = 100,
    temperature: float = 0.3,
    stop: Optional[list[str]] = None,
    seed: Optional[int] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
) -> str:
    """
    Complete a prompt using the llama.cpp endpoint via OpenAI client.
    
    Args:
        prompt: The input prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        stop: Stop sequences
        seed: Random seed for deterministic generation
        top_k: Top-k sampling parameter
        top_p: Top-p (nucleus) sampling parameter
        frequency_penalty: Frequency penalty for repetition
        presence_penalty: Presence penalty for repetition
    
    Returns:
        Generated text or empty string on failure
    """
    if stop is None:
        stop = ["\n\n", "User:", "Assistant:", "###"]
    
    client = OpenAI(
        base_url="http://127.0.0.1:8010/v1",
        api_key="not-needed"
    )
    
    for attempt in range(2):
        try:
            # Build kwargs with optional parameters
            kwargs = {
                "model": "default",  # llama.cpp uses "default" as model name
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stop": stop
            }
            
            # Add optional parameters if specified
            if seed is not None:
                kwargs["seed"] = seed
            if top_k is not None:
                kwargs["top_k"] = top_k
            if top_p is not None:
                kwargs["top_p"] = top_p
            if frequency_penalty is not None:
                kwargs["frequency_penalty"] = frequency_penalty
            if presence_penalty is not None:
                kwargs["presence_penalty"] = presence_penalty
            
            response = client.completions.create(**kwargs)
            return response.choices[0].text
        except ConnectionError as e:
            print(f"Connection error (attempt {attempt + 1}/2): {e}", file=sys.stderr)
            if attempt == 0:
                time.sleep(0.5)
            else:
                return ""
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}", file=sys.stderr)
            return ""
        except Exception as e:
            # Check for 5xx errors
            error_str = str(e)
            if "500" in error_str or "501" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
                print(f"Server error (attempt {attempt + 1}/2): {e}", file=sys.stderr)
                if attempt == 0:
                    time.sleep(0.5)
                else:
                    return ""
            else:
                print(f"Error: {e}", file=sys.stderr)
                return ""
    
    return ""


def complete_deterministic(
    prompt: str,
    max_tokens: int = 100,
    stop: Optional[list[str]] = None,
    seed: int = 1337
) -> str:
    """
    Complete a prompt with deterministic settings for reproducible output.
    
    Args:
        prompt: Input prompt
        max_tokens: Maximum tokens to generate
        stop: Stop sequences
        seed: Random seed (default: 1337)
        
    Returns:
        Generated text or empty string on failure
    """
    return complete(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=0.0,
        stop=stop,
        seed=seed,
        top_k=0,  # Greedy sampling
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )


if __name__ == "__main__":
    result = complete("Say 'ready'.")
    print(result)
    sys.exit(0 if result else 2)