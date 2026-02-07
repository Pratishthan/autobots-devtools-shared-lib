# Contributing to Autobots DevTools Shared Library

Thank you for your interest in contributing to this project!

## Development Setup

1. **Clone and setup the workspace**
   ```bash
   # Ensure you're in the pk-multi workspace with .venv setup
   cd autobots-devtools-shared-lib
   ```

2. **Install dependencies**
   ```bash
   make install-dev
   ```

3. **Install pre-commit hooks** (requires git repository)
   ```bash
   make install-hooks
   ```

## Development Workflow

### Making Changes

1. Create a new branch for your feature or bugfix
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style

3. Run all checks before committing
   ```bash
   make all-checks
   ```

### Code Quality Standards

This project maintains high code quality standards:

- **Type annotations** - All code should have type annotations (Pyright basic mode)
- **Comprehensive tests** - Aim for >90% code coverage
- **Clean code** - Pass all Ruff linting rules
- **Consistent formatting** - Use Ruff formatter (line length: 100)

### Running Tests

```bash
# Run all tests with coverage
make test-cov

# Run tests without coverage (faster)
make test-fast

# Run specific test
make test-one TEST=tests/unit/test_example.py::test_function
```

### Code Formatting

```bash
# Format your code
make format

# Check formatting without changes
make check-format
```

### Type Checking

```bash
# Run Pyright type checker
make type-check
```

### Linting

```bash
# Run linter with auto-fix
make lint
```

## Pre-commit Hooks

Pre-commit hooks automatically run on every commit to ensure code quality:

- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON/TOML validation
- Ruff linting and formatting
- Pyright type checking
- Pytest unit tests

To run hooks manually on all files:

```bash
make pre-commit
```

## Project Structure

```
autobots-devtools-shared-lib/
├── src/
│   └── autobots_devtools_shared_lib/  # Main package
│       ├── __init__.py                 # Package initialization
│       ├── py.typed                    # PEP 561 marker for type stubs
│       ├── chainlit_ui/                # Chainlit UI components
│       ├── dynagent/                   # Dynagent framework
│       ├── llm_tools/                  # LLM tool integrations
│       └── observability/              # Observability helpers
├── tests/                              # Test files
│   ├── conftest.py                     # Pytest configuration
│   ├── unit/                           # Unit tests
│   ├── integration/                    # Integration tests
│   └── e2e/                            # End-to-end tests
├── .pre-commit-config.yaml             # Pre-commit hooks config
├── pyproject.toml                      # Project & tool configuration
├── poetry.toml                         # Poetry settings
├── Makefile                            # Development commands
└── README.md                           # Project documentation
```

## Adding New Dependencies

```bash
# Add a runtime dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Update all dependencies
make update-deps
```

## Testing Guidelines

- Write tests for all new functionality
- Use pytest fixtures for shared test data
- Mark slow tests with `@pytest.mark.slow`
- Mark integration tests with `@pytest.mark.integration`
- Mark unit tests with `@pytest.mark.unit`
- Aim for comprehensive test coverage

Example test:

```python
import pytest

@pytest.mark.unit
def test_example(sample_data: dict[str, str]) -> None:
    """Test example functionality."""
    assert sample_data["key"] == "value"
```

## Type Checking Guidelines

- All functions should have type annotations
- Use modern type hints (e.g., `list[str]` instead of `List[str]`)
- Use `typing.Protocol` for structural typing
- Use `typing.TYPE_CHECKING` for import-only types

Example:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

def process_items(items: Sequence[str]) -> list[str]:
    """Process a sequence of items."""
    return [item.upper() for item in items]
```

## Async Code Guidelines

This project uses async/await extensively. When writing async code:

- Use `async def` for async functions
- Always `await` async calls
- Use `pytest.mark.asyncio` for async tests
- Configure `asyncio_mode = "auto"` in pytest (already set)

Example:

```python
import pytest

@pytest.mark.asyncio
@pytest.mark.unit
async def test_async_function() -> None:
    """Test async functionality."""
    result = await some_async_function()
    assert result is not None
```

## Chainlit Integration

When working with Chainlit UI components:

- Follow Chainlit best practices for UI elements
- Test UI components in isolation when possible
- Use integration tests for full UI flows
- Document any new UI components

## Commit Message Guidelines

Use clear, descriptive commit messages:

```
Add feature X to support Y

- Implement core functionality
- Add comprehensive tests
- Update documentation
```

## Pull Request Process

1. Ensure all checks pass (`make all-checks`)
2. Update documentation if needed
3. Add/update tests as appropriate
4. Submit PR with clear description
5. Address review feedback

## Questions?

If you have questions or need help, please open an issue on the project repository.
