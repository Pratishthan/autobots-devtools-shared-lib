# Autobots DevTools Shared Library

Shared library functions to be used for all autobots projects. This library provides common functionality for Chainlit UI integration, LLM tools, Dynagent framework, and observability helpers.

## Features

- **Chainlit UI Integration**: Pre-built UI components for Chainlit applications
- **Dynagent Framework**: Framework for building dynamic AI agents
- **LLM Tools**: Reusable tools for language model integrations
- **Batch Processing**: Utilities for batch operations
- **Observability**: Logging and monitoring helpers

## Prerequisites

- Python 3.12+
- Poetry (install with `brew install poetry` on macOS)

## Workspace Setup

This library is part of a multi-repository workspace (`ws-multi`). Follow these steps to set up the workspace:

### 1. Clone the Workspace

```bash
# Clone or create the workspace directory
cd /Users/pralhad/work/src
git clone <pk-multi-workspace-url> ws-multi
cd ws-multi
```

### 2. Create Shared Virtual Environment

```bash
# From the workspace root
make setup
```

This creates a shared `.venv` at the workspace root that all repositories use.

### 3. Clone This Repository

```bash
# From workspace root
git clone https://github.com/Pratishthan/autobots-devtools-shared-lib.git
cd autobots-devtools-shared-lib
```

### 4. Install Dependencies

```bash
# Install with development dependencies
make install-dev

# Or install runtime dependencies only
make install
```

### 5. Install Pre-commit Hooks

```bash
make install-hooks
```

## Development

### Available Commands

Run these commands from the `autobots-devtools-shared-lib/` directory:

```bash
# Testing
make test              # Run tests with coverage
make test-cov          # Run tests with HTML coverage report
make test-fast         # Run tests without coverage (faster)
make test-one TEST=tests/unit/test_example.py::test_function

# Code Quality
make format            # Format code with Ruff
make lint              # Lint with Ruff (auto-fix enabled)
make check-format      # Check formatting without modifying
make type-check        # Run Pyright type checker
make all-checks        # Run all checks (format, type, test)

# Dependencies
make install           # Install runtime dependencies
make install-dev       # Install with dev dependencies
make update-deps       # Update dependencies

# Other
make clean             # Remove cache files and build artifacts
make build             # Build package
make help              # Show all available commands
```

### Workspace-Level Commands

From the workspace root (`/Users/pralhad/work/src/pk-multi/`):

```bash
make test           # Run tests across all repos
make lint           # Lint all repos
make format         # Format all repos
make type-check     # Type check all repos
make all-checks     # Run all checks across all repos
```

## Project Structure

```
autobots-devtools-shared-lib/
├── src/
│   └── autobots_devtools_shared_lib/
│       ├── __init__.py
│       ├── py.typed              # PEP 561 type stub marker
│       ├── chainlit_ui/          # Chainlit UI components
│       ├── dynagent/             # Dynagent framework
│       ├── llm_tools/            # LLM tool integrations
│       ├── observability/        # Observability helpers
│       └── batch_processing/     # Batch processing utilities
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
├── .github/workflows/            # GitHub Actions CI/CD
├── pyproject.toml                # Dependencies and tool config
├── poetry.toml                   # Poetry settings (uses workspace .venv)
├── Makefile                      # Development commands
├── CONTRIBUTING.md               # Contribution guidelines
└── PUBLISHING.md                 # PyPI publishing guide
```

## Code Quality Standards

This project maintains high code quality standards:

- **Type Safety**: Type annotations required (Pyright basic mode)
- **Testing**: Comprehensive test coverage with pytest
- **Formatting**: Ruff formatter (line length: 100)
- **Linting**: Ruff linter with strict rules
- **Pre-commit Hooks**: Automated checks on every commit

## Testing

```bash
# Run all tests
make test

# Run specific test file
make test-one TEST=tests/unit/test_example.py

# Run with coverage report
make test-cov
```

Tests are organized into:
- **Unit tests** (`tests/unit/`): Test individual functions and classes
- **Integration tests** (`tests/integration/`): Test component interactions
- **E2E tests** (`tests/e2e/`): Test complete workflows

## Type Checking

```bash
# Run Pyright type checker
make type-check
```

All code should have type annotations. The project uses Pyright in basic mode.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and workflow.

## Publishing

See [PUBLISHING.md](PUBLISHING.md) for instructions on publishing to PyPI.

## License

MIT

## Authors

- Pralhad <pralhad@example.com>

## Questions?

If you have questions or need help, please open an issue on the project repository.
