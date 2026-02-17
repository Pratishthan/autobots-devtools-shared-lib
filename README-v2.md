# Autobots DevTools Shared Library

**Dyn**amic **Agent** (**Dynagent**) is the core of this library. It turns your prompts and business processes into production-ready, multi-agent applications—chatbots and unsupervised workflows—in hours. You focus on prompts, output schemas, and domain logic; Dynagent handles multi-LLM wiring, UI integration, observability, and batch processing out of the box.

### Essential features

| Feature | Description |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dynagent framework** | Build dynamic AI agents with YAML configs, prompts, and tools. Agent handoff and default/coordinator agents for mesh-style flows. |
| **Multi-LLM support** | Swap LLMs like swapping batteries. Use Gemini, Claude, or others via a single integration layer. |
| **Chainlit UI** | Pre-built streaming, tool steps, and structured output for Chainlit. OAuth-ready. |
| **State & context** | Session state and context management with caching and durable storage. Tools receive `ToolRuntime` with shared state across handoffs. |
| **Batch processing** | Run prompts in parallel for batch-enabled agents. Sync API with `batch_invoker` and `BatchResult`. |
| **Observability** | Langfuse integration for tracing and monitoring. `TraceMetadata` for session, app, and tags. |
| **Pythonic** | Native Python and LangChain tools. Type hints, async/sync, pytest—no DSLs. |
| **Extensible** | File server, workspace management, Jenkins integration, and helpers that plug into the framework. |

## Quickstart

| Guide | Description |
| ------ | ----------- |
| **[Try Jarvis](https://github.com/Pratishthan/autobots-agents-jarvis)** | See Dynagent in action with a multi-domain multi-agent demo (Concierge, Customer Support, Sales). |
| **[Install](#workspace-setup)** | Set up the shared workspace, virtual environment, and install this library. |
| **[Development](#development)** | Run tests, format, lint, type-check, and use the Makefile from this repo or the workspace root. |

## How-to guides

| Guide | Description |
| ------ | ----------- |
| **[Workspace setup](#workspace-setup)** | Clone the workspace, create the shared `.venv`, clone this repo, and install dependencies. |
| **[Development](#development)** | Available `make` targets: test, format, lint, type-check, install, build, clean. |
| **[Project structure](#project-structure)** | Layout of `autobots_devtools_shared_lib` (dynagent, chainlit_ui, llm_tools, observability, batch). |
| **[Testing](#testing)** | Unit, integration, and e2e tests. Run with `make test`, `make test-fast`, or `make test-one`. |
| **[Contributing](#contributing)** | See CONTRIBUTING.md for guidelines and workflow. |
| **[Publishing](#publishing)** | See PUBLISHING.md for PyPI publishing. |

## Advanced

| Topic | Description |
| ------ | ----------- |
| **[Code quality](#code-quality-standards)** | Type safety (Pyright), pytest, Ruff format/lint, pre-commit hooks. |
| **[Type checking](#type-checking)** | Pyright in basic mode; type annotations required. |
| **[Workspace commands](#workspace-level-commands)** | From workspace root: `make test`, `make lint`, `make format`, `make type-check`, `make all-checks` across all repos. |

---

## Workspace setup

This library is part of a multi-repository workspace. Use a shared virtual environment at the workspace root.

**Prerequisites:** Python 3.12+, Poetry (e.g. `brew install poetry` on macOS).

### 1. Clone the workspace

```bash
cd /path/to/your/work
git clone <workspace-url> ws-jarvis
cd ws-jarvis
```

### 2. Create shared virtual environment

```bash
make setup
```

This creates a shared `.venv` at the workspace root.

### 3. Clone this repository

```bash
git clone https://github.com/Pratishthan/autobots-devtools-shared-lib.git
cd autobots-devtools-shared-lib
```

### 4. Install dependencies

```bash
make install-dev   # with dev dependencies (recommended)
# or
make install       # runtime only
```

### 5. Pre-commit hooks

```bash
make install-hooks
```

## Development

Run from `autobots-devtools-shared-lib/`:

```bash
# Testing
make test              # with coverage
make test-fast         # no coverage
make test-one TEST=tests/unit/test_example.py::test_function

# Code quality
make format            # Ruff format
make lint              # Ruff lint (auto-fix)
make check-format      # check only
make type-check        # Pyright
make all-checks        # format, type, test

# Dependencies & build
make install / make install-dev / make update-deps
make build
make clean
make help
```

### Workspace-level commands

From the workspace root:

```bash
make test
make lint
make format
make type-check
make all-checks
```

## Project structure

```
autobots-devtools-shared-lib/
├── src/autobots_devtools_shared_lib/
│   ├── dynagent/           # Multi-agent framework
│   ├── chainlit_ui/        # Chainlit UI components
│   ├── llm_tools/          # LLM integrations
│   ├── observability/      # Observability helpers
│   └── batch_processing/   # Batch utilities
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .github/workflows/
├── pyproject.toml
├── Makefile
├── CONTRIBUTING.md
└── PUBLISHING.md
```

## Code quality standards

- **Type safety:** Type annotations; Pyright (basic mode).
- **Testing:** pytest; unit, integration, e2e.
- **Formatting:** Ruff, line length 100.
- **Linting:** Ruff, strict rules.
- **Pre-commit:** Format, lint, type-check, tests on commit.

## Testing

```bash
make test
make test-one TEST=tests/unit/test_example.py
make test-cov   # HTML coverage report
```

- **Unit** (`tests/unit/`): Functions and classes.
- **Integration** (`tests/integration/`): Component interactions.
- **E2E** (`tests/e2e/`): Full workflows.

## Type checking

```bash
make type-check
```

All code must have type annotations. Pyright runs in basic mode.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and guidelines.

## Publishing

See [PUBLISHING.md](PUBLISHING.md) for PyPI publishing.

## License

MIT

## Authors

- **Pra1had** — [GitHub](https://github.com/pra1had) · pralhad.kamath@pratishthanventures.com

## Questions?

Open an issue on the project repository.
