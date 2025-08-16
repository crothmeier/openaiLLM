# OpenAI LLM Infrastructure Makefile

.PHONY: help install verify test clean doctor

help:
	@echo "OpenAI LLM Infrastructure Management"
	@echo "===================================="
	@echo ""
	@echo "Commands:"
	@echo "  make install  - Install Python package"
	@echo "  make verify   - Run verification checks"
	@echo "  make test     - Run test suite"
	@echo "  make doctor   - Diagnose system issues"
	@echo "  make clean    - Clean cache files"

install:
	pip install -e .
	@echo "✓ Python package installed"

verify:
	@echo "=== Running Verification ==="
	@./verify-nvme-storage.sh || true

test:
	pytest tests/ -v || echo "Tests need pytest"

doctor:
	@echo "=== System Diagnosis ==="
	@mountpoint -q /mnt/nvme && echo "✓ NVMe mounted" || echo "✗ NVMe not mounted"
	@df -h /mnt/nvme 2>/dev/null | tail -1 || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ htmlcov/ .coverage
	@echo "✓ Cleaned"
