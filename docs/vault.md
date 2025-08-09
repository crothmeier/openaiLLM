# Vault Integration for Secrets Management

This document provides instructions for integrating HashiCorp Vault for secure secrets management in the OpenAI LLM infrastructure.

## Overview

We use Vault for:
- Dynamic secrets generation with short-lived tokens
- GitHub OIDC integration for CI/CD authentication
- Application secrets storage using KV v2 engine
- Audit logging of all secret access

## Prerequisites

- HashiCorp Vault instance (1.15+ recommended)
- Python with `hvac` library installed
- GitHub repository with OIDC provider configured

## Setup Instructions

### 1. Install Dependencies

```bash
pip install hvac
```

### 2. Configure Vault KV v2 Engine

```bash
# Enable KV v2 secrets engine
vault secrets enable -path=openai-llm kv-v2

# Write initial secrets
vault kv put openai-llm/api-keys \
    huggingface_token=hf_xxxx \
    openai_key=sk-xxxx \
    anthropic_key=sk-ant-xxxx
```

### 3. GitHub OIDC Configuration

Configure Vault to accept GitHub Actions OIDC tokens:

```bash
# Enable JWT auth method
vault auth enable jwt

# Configure GitHub OIDC
vault write auth/jwt/config \
    bound_issuer="https://token.actions.githubusercontent.com" \
    oidc_discovery_url="https://token.actions.githubusercontent.com"

# Create role for GitHub Actions
vault write auth/jwt/role/github-actions \
    bound_audiences="https://github.com/<org>" \
    bound_subject="repo:<org>/<repo>:ref:refs/heads/main" \
    user_claim="actor" \
    role_type="jwt" \
    policies="openai-llm-ci" \
    ttl=15m
```

### 4. Create Vault Policy

```hcl
# openai-llm-ci.hcl
path "openai-llm/data/*" {
  capabilities = ["read", "list"]
}

path "auth/token/create" {
  capabilities = ["create", "update"]
}
```

Apply the policy:

```bash
vault policy write openai-llm-ci openai-llm-ci.hcl
```

### 5. GitHub Actions Integration

Add to your GitHub workflow:

```yaml
- name: Get Vault Token
  id: vault-auth
  run: |
    VAULT_TOKEN=$(vault write -field=token auth/jwt/login \
      role=github-actions \
      jwt=${{ secrets.GITHUB_TOKEN }})
    echo "::add-mask::$VAULT_TOKEN"
    echo "vault_token=$VAULT_TOKEN" >> $GITHUB_OUTPUT

- name: Retrieve Secrets
  env:
    VAULT_TOKEN: ${{ steps.vault-auth.outputs.vault_token }}
  run: |
    vault kv get -format=json openai-llm/api-keys
```

## Python Integration Examples

### Basic KV v2 Operations

```python
import hvac
import os
from typing import Dict, Any

class VaultSecretManager:
    """Manage secrets using HashiCorp Vault KV v2 engine."""
    
    def __init__(self, vault_url: str = None, token: str = None):
        """Initialize Vault client.
        
        Args:
            vault_url: Vault server URL (defaults to VAULT_ADDR env var)
            token: Vault token (defaults to VAULT_TOKEN env var)
        """
        self.vault_url = vault_url or os.environ.get('VAULT_ADDR', 'https://vault.example.com')
        self.token = token or os.environ.get('VAULT_TOKEN')
        
        if not self.token:
            raise ValueError("Vault token required via parameter or VAULT_TOKEN env var")
        
        self.client = hvac.Client(url=self.vault_url, token=self.token)
        
        if not self.client.is_authenticated():
            raise ValueError("Failed to authenticate with Vault")
        
        self.mount_point = 'openai-llm'
    
    def read_secret(self, path: str) -> Dict[str, Any]:
        """Read secret from KV v2 engine.
        
        Args:
            path: Secret path (e.g., 'api-keys')
        
        Returns:
            Dictionary containing secret data
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point
            )
            return response['data']['data']
        except hvac.exceptions.InvalidPath:
            raise ValueError(f"Secret not found at path: {path}")
    
    def write_secret(self, path: str, secret_data: Dict[str, Any]) -> None:
        """Write secret to KV v2 engine.
        
        Args:
            path: Secret path
            secret_data: Dictionary of secret key-value pairs
        """
        self.client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=secret_data,
            mount_point=self.mount_point
        )
    
    def list_secrets(self, path: str = '') -> list:
        """List secrets at given path.
        
        Args:
            path: Path to list (defaults to root)
        
        Returns:
            List of secret keys
        """
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point
            )
            return response['data']['keys']
        except hvac.exceptions.InvalidPath:
            return []
    
    def delete_secret(self, path: str) -> None:
        """Delete secret and all its versions.
        
        Args:
            path: Secret path to delete
        """
        self.client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=path,
            mount_point=self.mount_point
        )
    
    def get_api_key(self, service: str) -> str:
        """Get API key for specific service.
        
        Args:
            service: Service name (e.g., 'huggingface', 'openai')
        
        Returns:
            API key string
        """
        secrets = self.read_secret('api-keys')
        key_name = f"{service}_token" if service == 'huggingface' else f"{service}_key"
        
        if key_name not in secrets:
            raise ValueError(f"API key not found for service: {service}")
        
        return secrets[key_name]

# Usage example for model_runner
def get_model_credentials():
    """Retrieve model API credentials from Vault."""
    try:
        vault = VaultSecretManager()
        
        # Get HuggingFace token
        hf_token = vault.get_api_key('huggingface')
        os.environ['HF_TOKEN'] = hf_token
        
        # Get other API keys as needed
        openai_key = vault.get_api_key('openai')
        
        return {
            'huggingface': hf_token,
            'openai': openai_key
        }
    except Exception as e:
        print(f"Failed to retrieve credentials from Vault: {e}")
        raise

# Dynamic token generation example
def get_short_lived_token(vault_client: hvac.Client, ttl: str = "1h") -> str:
    """Generate short-lived token for temporary access.
    
    Args:
        vault_client: Authenticated Vault client
        ttl: Token time-to-live (e.g., "1h", "30m")
    
    Returns:
        Short-lived token string
    """
    response = vault_client.auth.token.create(
        policies=['openai-llm-readonly'],
        ttl=ttl,
        renewable=True
    )
    return response['auth']['client_token']
```

### Integration with Model Runner

```python
# model_runner.py example integration
import asyncio
from vault_secrets import VaultSecretManager

async def initialize_model_with_vault():
    """Initialize model with credentials from Vault."""
    vault = VaultSecretManager()
    
    # Retrieve API credentials
    credentials = vault.read_secret('api-keys')
    
    # Set environment variables for model libraries
    os.environ['HUGGINGFACE_TOKEN'] = credentials.get('huggingface_token', '')
    
    # Initialize model with secured credentials
    # TODO: Implement actual model initialization
    print("Model initialized with Vault-managed credentials")

# Run: asyncio.run(initialize_model_with_vault())
```

## Security Best Practices

1. **Token Rotation**: Implement automatic token rotation every 24-48 hours
2. **Least Privilege**: Use minimal required permissions in Vault policies
3. **Audit Logging**: Enable Vault audit logging for all secret access
4. **Environment Isolation**: Use separate Vault namespaces for dev/staging/prod
5. **Secret Versioning**: Leverage KV v2 versioning for secret history
6. **Dynamic Secrets**: Use dynamic credentials where possible (database, cloud providers)

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify VAULT_TOKEN environment variable is set
   - Check token hasn't expired: `vault token lookup`

2. **Secret Not Found**
   - Verify mount point: `vault secrets list`
   - Check path: `vault kv list openai-llm/`

3. **Permission Denied**
   - Review token policies: `vault token lookup`
   - Check policy permissions match required paths

## References

- [Vault KV v2 Documentation](https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2)
- [hvac Python Library](https://github.com/hvac/hvac)
- [GitHub OIDC with Vault](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-hashicorp-vault)