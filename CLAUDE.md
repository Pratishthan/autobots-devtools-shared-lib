# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**bro-chat** (Business Requirement Oracle) is an AI-powered agent that helps Product Owners create and manage Component Vision Documents through interactive, section-based conversations. It uses LangChain/LangGraph for agent orchestration and Google Gemini as the LLM backend.

## Development Commands

```bash
# Install dependencies
uv sync

# Run the dynamic agent directly
uv run python src/bro_chat/agents/dynagent.py

# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e

# Run a single test file
uv run pytest tests/unit/test_settings.py -v

# Run a single test
uv run pytest tests/unit/test_settings.py::test_settings_from_env -v

# Linting and formatting
uv run ruff check .
uv run ruff format .
uv run ruff check --fix .

# Type checking
uv run pyright

# Run pre-commit hooks manually
uv run pre-commit run --all-files

# Docker
docker-compose up --build
```

## Architecture

### Core Components

```
src/bro_chat/
├── config/settings.py     # Pydantic settings from env vars
├── agents/
│   ├── dynagent.py        # LangGraph dynamic agent with step-based middleware
│   └── tools.py           # Custom tools (Search, Calculator)
├── utils/files.py         # File I/O tools + prompt loading
└── observability/tracing.py  # Langfuse integration
```

### Agent System (dynagent.py)

The dynamic agent follows a **step-based middleware pattern**:

1. `DynamicAgentState` - Custom state tracking workflow steps
2. `STEP_CONFIG` - Maps step names to prompts, tools, and requirements
3. `apply_step_config` - Middleware that configures agent behavior per step
4. `handoff` tool - Manages transitions between steps
5. `SummarizationMiddleware` - Automatic message summarization

Each step has: a prompt (from `prompts/` directory), a set of tools, and required state fields.

### Configuration

Settings are managed via Pydantic BaseSettings in `config/settings.py`. Required:
- `GOOGLE_API_KEY` - For Gemini LLM

Optional:
- `LANGFUSE_*` - Observability tracing
- `DEBUG` - Enable debug logging

### Testing Structure

- **Unit tests** (`tests/unit/`) - Settings, utilities
- **Integration tests** (`tests/integration/`) - Agent creation, tool functionality
- **E2E tests** (`tests/e2e/`) - Full chat flow

Use `requires_google_api` marker to skip tests needing real API key:
```python
@requires_google_api
def test_needs_real_api():
    ...
```

## Key Files

| File | Purpose |
|------|---------|
| `src/bro_chat/agents/dynagent.py` | Primary agent implementation pattern |
| `docs/living-docs/specs/bro-agent-spec.md` | Full bro agent specification |
| `docs/living-docs/toc.md` | Vision document table of contents structure |
| `prompts/designer/*.md` | Agent prompts (loaded via `load_prompt()`) |

## Code Conventions

- All source files start with 2-line ABOUTME comments explaining purpose
- Use `uv` for all Python commands
- Pre-commit hooks run: ruff (lint/format), pyright (type check), pytest (unit tests)
- Async throughout - use `pytest-asyncio` with `asyncio_mode = "auto"`

## Adding New Agent Steps

1. Create prompt file in `prompts/` directory
2. Add step to `AgentList` literal type in dynagent.py
3. Add configuration to `STEP_CONFIG` dict
4. Implement any step-specific tools
