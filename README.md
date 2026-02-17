# Motivation

The author team spent a lot time researching open source frameworks to convert "working" prompts into production ready application. So we embarked on the journey to help you in your **ViberEnt** (read vibrant)- *Vibe Coder for Enterprise* journey.

# Introduction

**Dyn**amic **Agent** (**DynAgent**) framework - the core of the **Autobots DevTools Shared Library** (ADSL) package - provides supporting capabilities for turning your agent AI automation workflows into enterprise grade apps that can run production workloads. You can convert a business process into an LLM assisted UI chatbot and/or unsupervised workflow in an order of **hours**, even lesser if you have your prompts handy. DynAgent handles the heavy lifting for you out of the box: multi LLM, chatbot, observabilit and more, while you to focus on your prompts, output schemas and converting business process into works.

## Features

- **DynAgent Framework**: Framework for building dynamic AI agents
- **Multi LLM Support**: Swap LLMs like swapping batteries
- **Chainlit UI Integration**: Pre-built UI components for Chainlit applications
- **OAUTH Integration**: Chainlit UI can be
- **LLM Tools**: Reusable tools for language model integrations
- **Batch Processing**: Utilities for batch operations
- **Observability**: Logging and monitoring helpers
- **Containerization**: Docker images with bundled dependencies
- **Prompt Versioning**: Prompts as source model
- **Prompt Evaluation**: Enables tweaking prompts

## Batteries Included

It also provides a suite of helpers that work seamlessly with the DynAgent framework

## Helper

- **File Server** -
- **Workspace Management** -
- **Context Management** - with caching and durable storage
- **Jenkins Integration** -

# Quickstart

Want to see DynAgent in action - head to **[Jarvis](https://github.com/Pratishthan/autobots-agents-jarvis)**


# Contributing

If you are interested in adding more features to DynAgent then follow the next section.

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
│       ├── DynAgent/             # DynAgent framework
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

- Pra1had
  - Email: <pralhad.kamath@pratishthanventures.com>
  - [Github:pra1had](https://github.com/pra1had)

## Questions?

If you have questions or need help, please open an issue on the project repository.
