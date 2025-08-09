"""Setup script for NVMe Model Storage CLI."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()

# Read version from package
version = "1.0.0"
init_path = Path(__file__).parent / "nvme_models" / "__init__.py"
if init_path.exists():
    with open(init_path, "r") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

setup(
    name="nvme-models",
    version=version,
    author="NVMe Model Storage Team",
    description="CLI tool for managing AI model storage on NVMe drives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/nvme-model-storage",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "rich>=10.0.0",
        "pyyaml>=5.4.0",
        "requests>=2.25.0",
        "huggingface-hub>=0.16.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "pytest-mock>=3.6.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "vllm": [
            "vllm>=0.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "nvme-models=nvme_models.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Hardware",
        "Topic :: System :: Systems Administration",
    ],
    keywords="nvme storage ai models huggingface ollama vllm cli",
)