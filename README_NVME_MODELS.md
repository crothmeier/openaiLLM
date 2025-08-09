# NVMe Model Storage - Python CLI Tool

## Overview

This repository has been refactored to include a modular Python CLI tool (`nvme-models`) for managing AI model storage on NVMe drives. The new implementation provides a clean, extensible architecture while maintaining backward compatibility with existing scripts.

## Features

- **Modular Python Architecture**: Clean separation of concerns with dedicated modules for storage, validation, configuration, and provider handlers
- **Multi-Provider Support**: HuggingFace, Ollama, and vLLM model management
- **Rich CLI Interface**: User-friendly commands with progress indicators and formatted output
- **Configuration Management**: YAML-based configuration with environment variable overrides
- **Input Validation**: Comprehensive validation for model IDs, paths, and disk space
- **Backward Compatibility**: Wrapper scripts ensure existing workflows continue to function

## Installation

### Install the CLI tool:

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## Usage

### Initialize NVMe Storage

```bash
nvme-models setup
```

This will:
- Create directory structure (`/mnt/nvme/hf-cache`, `/mnt/nvme/models`, `/mnt/nvme/ollama`)
- Set up environment variables
- Create symlinks for backward compatibility

### Download Models

#### HuggingFace Models
```bash
nvme-models download meta-llama/Llama-2-7b-hf --provider hf
```

#### Ollama Models
```bash
nvme-models download llama2:7b --provider ollama
```

### Verify Configuration

```bash
nvme-models verify

# JSON output for automation
nvme-models verify --format json
```

### List Downloaded Models

```bash
nvme-models list

# Filter by provider
nvme-models list --provider hf
```

### Clean Temporary Files

```bash
nvme-models clean
```

### Get Model Information

```bash
nvme-models info model-name --provider hf
```

## Project Structure

```
nvme_models/
├── __init__.py          # Package initialization
├── cli.py               # Click-based CLI entry point
├── config.py            # Configuration management
├── storage.py           # NVMe storage operations
├── validators.py        # Input validation logic
├── models/              # Provider-specific handlers
│   ├── __init__.py
│   ├── huggingface.py   # HuggingFace provider
│   ├── ollama.py        # Ollama provider
│   └── vllm.py          # vLLM provider
└── tests/               # Test suite
    └── test_cli.py      # CLI command tests
```

## Configuration

The tool uses a YAML configuration file (`config.yaml`):

```yaml
storage:
  nvme_path: /mnt/nvme
  require_mount: true
  min_free_space_gb: 50

providers:
  huggingface:
    cache_dir: ${nvme_path}/hf-cache
    models_dir: ${nvme_path}/models
  ollama:
    models_dir: ${nvme_path}/ollama
  vllm:
    models_dir: ${nvme_path}/models
    cache_dir: ${nvme_path}/vllm-cache

monitoring:
  enable_metrics: true
  log_level: INFO
```

Configuration can be overridden with environment variables:
- `NVME_PATH`: Override NVMe base path
- `NVME_MIN_FREE_SPACE_GB`: Minimum free space requirement
- `NVME_LOG_LEVEL`: Logging level

## Backward Compatibility

Existing shell scripts continue to work through compatibility wrappers:

- `setup-nvme-models.sh` → Uses `nvme-models setup`
- `download-models.sh` → Interactive menu using CLI commands
- `verify-nvme-storage.sh` → Uses `nvme-models verify`

## Docker/Kubernetes Integration

### Docker Compose
The `docker-compose-ollama.yml` now includes an init container that verifies NVMe setup:

```yaml
services:
  nvme-setup:
    image: python:3.9-slim
    command: |
      # Verifies NVMe mount and creates directories
```

### Kubernetes
The `vllm-k8s-deployment.yaml` includes an init container for verification:

```yaml
initContainers:
- name: nvme-setup
  image: python:3.9-slim
  # Verifies NVMe storage before starting vLLM
```

## Testing

Run the test suite:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest

# Run specific test file
pytest nvme_models/tests/test_cli.py
```

## Health Checks

For monitoring and automation:

```bash
# Get JSON status for health checks
nvme-models verify --format json

# Example output:
{
  "status": "success",
  "errors": [],
  "warnings": [],
  "summary": {
    "nvme_mounted": true,
    "directories_created": true,
    "environment_configured": true,
    "model_files_found": 10
  }
}
```

## Migration from Shell Scripts

To migrate from the old shell scripts:

1. Install the Python CLI: `pip install -e .`
2. Existing scripts will automatically use the new CLI through compatibility wrappers
3. Update automation to use CLI commands directly for better performance

## Benefits of the Refactored Architecture

1. **Maintainability**: Clean, modular Python code is easier to maintain than shell scripts
2. **Extensibility**: Easy to add new providers or features
3. **Testing**: Comprehensive test coverage with pytest
4. **Error Handling**: Better error messages and validation
5. **User Experience**: Rich CLI with progress indicators and formatted output
6. **Configuration**: Flexible YAML-based configuration
7. **Type Safety**: Python type hints improve code quality

## Requirements

- Python 3.8+
- Click 8.0+
- Rich 10.0+
- PyYAML 5.4+
- huggingface-hub 0.16+ (for HuggingFace support)

## License

MIT