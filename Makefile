.PHONY: help install install-dev install-hooks test test-cov lint format check-format type-check clean all-checks build publish file-server

# Default target
help:
	@echo "Available commands:"
	@echo "  make install          - Install project dependencies"
	@echo "  make install-dev      - Install project with dev dependencies"
	@echo "  make install-hooks    - Install pre-commit hooks"
	@echo "  make test             - Run tests"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make test-fast        - Run tests without coverage"
	@echo "  make lint             - Run ruff linter with auto-fix"
	@echo "  make format           - Format code with ruff"
	@echo "  make check-format     - Check code formatting without modifying"
	@echo "  make type-check       - Run pyright type checker"
	@echo "  make all-checks       - Run all checks (lint, format, type-check, test)"
	@echo "  make pre-commit       - Run pre-commit hooks on all files"
	@echo "  make clean            - Remove cache files and build artifacts"
	@echo "  make build            - Build the package"
	@echo "  make publish          - Publish package to PyPI"
	@echo "  make update-deps      - Update dependencies"
	@echo "  make file-server      - Run local file server on port 9002 (for testing fserver_client)"

# Use system/global poetry and tools from parent venv
VENV = ../.venv
PYTHON = $(VENV)/bin/python
POETRY = poetry
PRE_COMMIT = $(VENV)/bin/pre-commit
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
PYRIGHT = $(VENV)/bin/pyright

# Install project dependencies
install:
	$(POETRY) install --only main

# Install project with dev dependencies
install-dev:
	$(POETRY) install

# Install pre-commit hooks
install-hooks:
	$(PRE_COMMIT) install
	$(PRE_COMMIT) install --hook-type commit-msg

# Run tests
test:
	$(PYTEST)

# Run tests with coverage
test-cov:
	$(PYTEST) --cov --cov-report=term-missing --cov-report=html

# Run tests without coverage (faster)
test-fast:
	$(PYTEST) --no-cov -x

# Run specific test
test-one:
	@if [ -z "$(TEST)" ]; then \
		echo "Usage: make test-one TEST=path/to/test_file.py::test_function"; \
	else \
		$(PYTEST) $(TEST); \
	fi

# Run ruff linter with auto-fix
lint:
	$(RUFF) check --fix .

# Format code with ruff
format:
	$(RUFF) format .

# Check code formatting without modifying
check-format:
	$(RUFF) format --check .
	$(RUFF) check .

# Run pyright type checker
type-check:
	$(PYRIGHT) src/

# Run all checks
all-checks: check-format type-check test

# Run pre-commit hooks on all files
pre-commit:
	$(PRE_COMMIT) run --all-files

# Clean cache and build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	rm -rf dist/ build/

# Build the package
build:
	$(POETRY) build

# Publish to PyPI (requires authentication)
publish:
	$(POETRY) publish

# Update dependencies
update-deps:
	$(POETRY) update

# Show outdated dependencies
show-outdated:
	$(POETRY) show --outdated

# Export requirements.txt
export-requirements:
	$(POETRY) export -f requirements.txt --output requirements.txt --without-hashes
	$(POETRY) export -f requirements.txt --output requirements-dev.txt --with dev --without-hashes

# Run local file server (install deps first: pip install -r local_file_server/requirements-file-server.txt)
FILE_SERVER_PORT ?= 9002
file-server:
	$(PYTHON) -m uvicorn local_file_server.app:app --reload --host 0.0.0.0 --port $(FILE_SERVER_PORT)
