#!/usr/bin/env python3
"""Direct HTTP client for llama.cpp server."""

import sys
import json
from typing import Optional, List, Dict, Any
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)


class GPTOSSException(Exception):
    """Base exception for GPTOSS client errors."""
    pass


class GPTOSSTransportError(GPTOSSException):
    """Transport/network related errors."""
    pass


class GPTOSSJSONError(GPTOSSException):
    """JSON parsing errors."""
    pass


class GPTOSSSchemaError(GPTOSSException):
    """Response schema validation errors."""
    pass


class GPTOSSClient:
    """Direct HTTP client for llama.cpp server."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8010") -> None:
        """
        Initialize GPT-OSS client.
        
        Args:
            base_url: Base URL for the llama.cpp server
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = (2, 60)  # (connect, read) timeouts
    
    def _should_retry(self, exception: Exception) -> bool:
        """Check if request should be retried based on exception."""
        if isinstance(exception, requests.exceptions.RequestException):
            if hasattr(exception, 'response') and exception.response is not None:
                status = exception.response.status_code
                return status == 429 or (500 <= status < 600)
        return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            endpoint: API endpoint
            payload: Request payload
            
        Returns:
            Response JSON
            
        Raises:
            GPTOSSTransportError: On transport errors
            GPTOSSJSONError: On JSON parsing errors
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Check for retryable status codes
            if response.status_code == 429 or (500 <= response.status_code < 600):
                response.raise_for_status()
            
            # For other non-2xx status codes, raise without retry
            response.raise_for_status()
            
            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise GPTOSSJSONError(f"Failed to parse JSON response: {e}") from e
                
        except requests.exceptions.RequestException as e:
            # Check if this should be retried
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status == 429 or (500 <= status < 600):
                    raise  # Let tenacity handle retry
            raise GPTOSSTransportError(f"Request failed: {e}") from e
    
    def complete(
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.3,
        stop: Optional[List[str]] = None,
        stream: bool = False,
        seed: Optional[int] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        min_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        repeat_penalty: Optional[float] = None
    ) -> str:
        """
        Complete a prompt using the llama.cpp server.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop: Stop sequences
            stream: Whether to stream the response (not implemented)
            seed: Random seed for deterministic generation
            top_k: Top-k sampling parameter
            top_p: Top-p (nucleus) sampling parameter
            min_p: Minimum-p sampling parameter
            frequency_penalty: Frequency penalty for repetition
            presence_penalty: Presence penalty for repetition
            repeat_penalty: Repeat penalty (llama.cpp specific)
            
        Returns:
            Generated text
            
        Raises:
            GPTOSSTransportError: On network/transport errors
            GPTOSSJSONError: On JSON parsing errors
            GPTOSSSchemaError: On response schema validation errors
        """
        if stop is None:
            stop = ["\n\n", "###", "</end>"]
        
        payload = {
            "model": "default",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop,
            "stream": stream
        }
        
        # Add determinism parameters if specified
        if seed is not None:
            payload["seed"] = seed
        if top_k is not None:
            payload["top_k"] = top_k
        if top_p is not None:
            payload["top_p"] = top_p
        if min_p is not None:
            payload["min_p"] = min_p
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if repeat_penalty is not None:
            payload["repeat_penalty"] = repeat_penalty
        
        try:
            response = self._make_request("/v1/completions", payload)
        except RetryError as e:
            # Extract the original exception from RetryError
            if e.last_attempt.failed:
                original_exc = e.last_attempt.exception()
                if isinstance(original_exc, requests.exceptions.RequestException):
                    raise GPTOSSTransportError(f"Request failed after retries: {original_exc}") from original_exc
            raise
        
        # Validate response schema
        if not isinstance(response, dict):
            raise GPTOSSSchemaError(f"Response is not a dictionary: {type(response)}")
        
        if "choices" not in response:
            raise GPTOSSSchemaError("Missing 'choices' field in response")
        
        if not response["choices"]:
            raise GPTOSSSchemaError("Empty 'choices' array in response")
        
        choice = response["choices"][0]
        if "text" not in choice:
            raise GPTOSSSchemaError("Missing 'text' field in choice")
        
        return choice["text"]
    
    def complete_deterministic(
        self,
        prompt: str,
        max_tokens: int = 100,
        stop: Optional[List[str]] = None,
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
            Generated text
        """
        return self.complete(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.0,
            stop=stop,
            seed=seed,
            top_k=0,  # Greedy sampling
            top_p=1.0,
            min_p=0.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            repeat_penalty=1.0  # Neutral in llama.cpp
        )
    
    def instruct(self, instruction: str, context: str = "") -> str:
        """
        Execute an instruction using the Alpaca-style prompt format.
        
        Args:
            instruction: The instruction to execute
            context: Optional context/input for the instruction
            
        Returns:
            Generated response
            
        Raises:
            GPTOSSTransportError: On network/transport errors
            GPTOSSJSONError: On JSON parsing errors
            GPTOSSSchemaError: On response schema validation errors
        """
        if context:
            prompt = f"""### Instruction:
{instruction}

### Input:
{context}

### Response:
"""
        else:
            prompt = f"""### Instruction:
{instruction}

### Response:
"""
        
        return self.complete(
            prompt=prompt,
            max_tokens=200,  # Typically need more tokens for instructions
            temperature=0.3,
            stop=["\n\n", "###", "</end>", "\n### "]
        )


if __name__ == "__main__":
    try:
        client = GPTOSSClient()
        
        # Test complete()
        print("Testing complete():")
        print("-" * 40)
        result = client.complete("The capital of France is", max_tokens=20)
        print(f"Result: {result}")
        print()
        
        # Test instruct()
        print("Testing instruct():")
        print("-" * 40)
        result = client.instruct(
            "Summarize the following text in one sentence",
            "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991."
        )
        print(f"Result: {result}")
        
        sys.exit(0)
        
    except (GPTOSSTransportError, GPTOSSJSONError, GPTOSSSchemaError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)