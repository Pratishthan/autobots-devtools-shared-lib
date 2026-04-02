# MCP Integration Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic MCP client integration layer to dynagent, with Atlassian as the first bundled server and an example config showing usage.

**Architecture:** New `dynagent/mcp/` subpackage with four modules: config (types), registry (server definitions), session_manager (per-session connection lifecycle), and tool_adapter (MCP-to-LangChain bridge via namespaced placeholders). The only change to existing code is a small branch in `get_tool_map()` to resolve dotted tool names as MCP placeholders.

**Tech Stack:** Python 3.12, MCP SDK 1.26.0 (`mcp` package — already installed), LangChain StructuredTool, pytest

**Spec:** `docs/design/2026-03-27-mcp-integration-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py` | Public API exports |
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/config.py` | `McpTransport` enum, `McpServerConfig` dataclass, `load_mcp_config()` |
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/registry.py` | `McpServerRegistry` singleton |
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/session_manager.py` | `McpSessionManager` — per-session MCP client lifecycle |
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/tool_adapter.py` | `create_mcp_placeholder()` — wraps MCP tools as LangChain tools |
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/servers/__init__.py` | Bundled server auto-registration |
| Create | `src/autobots_devtools_shared_lib/dynagent/mcp/servers/atlassian.py` | Atlassian MCP server config |
| Modify | `src/autobots_devtools_shared_lib/dynagent/models/state.py:9-14` | Add `mcp_auth` field to `Dynagent` |
| Modify | `src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py:192-217` | Add MCP branch in `get_tool_map()` |
| Modify | `src/autobots_devtools_shared_lib/dynagent/__init__.py` | Export `register_mcp_servers`, `McpServerConfig`, `McpTransport` |
| Modify | `pyproject.toml:11-27` | Add `mcp>=1.26.0` to dependencies |
| Create | `tests/unit/mcp/__init__.py` | Test package |
| Create | `tests/unit/mcp/test_config.py` | Tests for config types and `load_mcp_config()` |
| Create | `tests/unit/mcp/test_registry.py` | Tests for `McpServerRegistry` |
| Create | `tests/unit/mcp/test_session_manager.py` | Tests for `McpSessionManager` |
| Create | `tests/unit/mcp/test_tool_adapter.py` | Tests for `create_mcp_placeholder()` |
| Create | `tests/unit/mcp/test_get_tool_map_mcp.py` | Tests for the `get_tool_map()` MCP branch |
| Create | `configs/mcp-example/agents.yaml` | Example agents.yaml showing MCP tool usage |

---

### Task 1: Add `mcp` dependency to pyproject.toml

**Files:**
- Modify: `pyproject.toml:11-27`

- [ ] **Step 1: Add mcp to dependencies**

In `pyproject.toml`, add `mcp` to the `dependencies` list:

```toml
dependencies = [
    "chainlit>=2.9.6",
    "jsonschema>=4.26.0",
    "langchain>=1.0.0",
    "langchain-anthropic>=1.4.0",
    "langchain-google-genai>=4.2.0",
    "langfuse>=3.12.1",
    "mcp>=1.26.0",
    "pydantic-settings>=2.10.1",
    "python-dotenv>=1.1.1",
    "pyyaml>=6.0.3",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "opentelemetry-api>=1.30.0,<2.0.0",
    "opentelemetry-sdk>=1.30.0,<2.0.0",
    "opentelemetry-exporter-otlp-proto-http>=1.30.0,<2.0.0",
    "opentelemetry-instrumentation-fastapi>=0.49b0",
]
```

- [ ] **Step 2: Lock dependencies**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && poetry lock --no-update`

Expected: `poetry.lock` updated with `mcp` entry.

- [ ] **Step 3: Verify import**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws && .venv/bin/python -c "import mcp; print(mcp.__version__)"`

Expected: `1.26.0` (or higher)

- [ ] **Step 4: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add pyproject.toml poetry.lock
git commit -m "deps: add mcp>=1.26.0 to runtime dependencies"
```

---

### Task 2: Add `mcp_auth` field to Dynagent state

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/models/state.py:9-14`
- Create: `tests/unit/test_dynagent_state_mcp_auth.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_dynagent_state_mcp_auth.py`:

```python
# ABOUTME: Tests that Dynagent state supports the mcp_auth field for MCP token storage.
# ABOUTME: Validates typed dict accepts mcp_auth without breaking existing fields.

from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


def test_dynagent_accepts_mcp_auth_field():
    """Dynagent state should accept an mcp_auth dict for MCP token storage."""
    state: Dynagent = {
        "messages": [],
        "agent_name": "test",
        "session_id": "s1",
        "mcp_auth": {"atlassian": "token-abc"},
    }
    assert state["mcp_auth"] == {"atlassian": "token-abc"}


def test_dynagent_mcp_auth_is_optional():
    """mcp_auth should be optional — existing state without it must still work."""
    state: Dynagent = {
        "messages": [],
        "agent_name": "test",
    }
    assert "mcp_auth" not in state


def test_dynagent_mcp_auth_multiple_servers():
    """mcp_auth should support tokens for multiple MCP servers."""
    state: Dynagent = {
        "messages": [],
        "mcp_auth": {
            "atlassian": "token-a",
            "internal_api": "token-b",
        },
    }
    assert state["mcp_auth"]["atlassian"] == "token-a"
    assert state["mcp_auth"]["internal_api"] == "token-b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/test_dynagent_state_mcp_auth.py -v --no-cov`

Expected: FAIL — `mcp_auth` is not a valid key in the TypedDict.

- [ ] **Step 3: Add mcp_auth to Dynagent**

In `src/autobots_devtools_shared_lib/dynagent/models/state.py`, add the field:

```python
# ABOUTME: State schema for the dynagent reference architecture.
# ABOUTME: Dynagent holds agent_name, session_id, optional user_name, and MCP auth tokens.

from typing import NotRequired

from langchain.agents import AgentState


class Dynagent(AgentState):
    """Minimal agent state carrying routing keys and optional user identity."""

    agent_name: NotRequired[str]
    session_id: NotRequired[str]
    user_name: NotRequired[str]
    mcp_auth: NotRequired[dict[str, str]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/test_dynagent_state_mcp_auth.py -v --no-cov`

Expected: 3 passed.

- [ ] **Step 5: Run existing state tests to check no regression**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/test_dynagent_state.py -v --no-cov`

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/models/state.py tests/unit/test_dynagent_state_mcp_auth.py
git commit -m "feat: add mcp_auth field to Dynagent state for MCP token storage"
```

---

### Task 3: Create `McpTransport` and `McpServerConfig` types

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/config.py`
- Create: `tests/unit/mcp/__init__.py`
- Create: `tests/unit/mcp/test_config.py`

- [ ] **Step 1: Create test package**

Create `tests/unit/mcp/__init__.py` (empty file).

- [ ] **Step 2: Write failing tests for config types**

Create `tests/unit/mcp/test_config.py`:

```python
# ABOUTME: Tests for MCP config types: McpTransport enum and McpServerConfig dataclass.
# ABOUTME: Validates construction, defaults, and YAML config loading.

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import (
    McpServerConfig,
    McpTransport,
    load_mcp_config,
)


class TestMcpTransport:
    def test_stdio_value(self):
        assert McpTransport.STDIO.value == "stdio"

    def test_streamable_http_value(self):
        assert McpTransport.STREAMABLE_HTTP.value == "streamable_http"

    def test_from_string_stdio(self):
        assert McpTransport("stdio") == McpTransport.STDIO

    def test_from_string_streamable_http(self):
        assert McpTransport("streamable_http") == McpTransport.STREAMABLE_HTTP


class TestMcpServerConfig:
    def test_minimal_stdio_config(self):
        cfg = McpServerConfig(
            name="test",
            transport=McpTransport.STDIO,
            command="echo",
        )
        assert cfg.name == "test"
        assert cfg.transport == McpTransport.STDIO
        assert cfg.command == "echo"
        assert cfg.args is None
        assert cfg.env is None
        assert cfg.url is None
        assert cfg.auth_state_key is None

    def test_full_stdio_config(self):
        cfg = McpServerConfig(
            name="atlassian",
            transport=McpTransport.STDIO,
            command="npx",
            args=["@anthropic/atlassian-mcp-server"],
            env={"NODE_ENV": "production"},
            auth_state_key="atlassian",
        )
        assert cfg.args == ["@anthropic/atlassian-mcp-server"]
        assert cfg.env == {"NODE_ENV": "production"}
        assert cfg.auth_state_key == "atlassian"

    def test_streamable_http_config(self):
        cfg = McpServerConfig(
            name="remote",
            transport=McpTransport.STREAMABLE_HTTP,
            url="https://mcp.example.com/api",
            auth_state_key="remote",
        )
        assert cfg.url == "https://mcp.example.com/api"
        assert cfg.transport == McpTransport.STREAMABLE_HTTP


class TestLoadMcpConfig:
    def test_returns_empty_dict_when_no_mcp_servers_section(self, tmp_path, monkeypatch):
        """agents.yaml without mcp_servers section returns {}."""
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text("agents:\n  coordinator:\n    prompt: test\n    tools: []\n")
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert result == {}

    def test_loads_mcp_servers_section(self, tmp_path, monkeypatch):
        """agents.yaml with mcp_servers section returns parsed entries."""
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text(
            "mcp_servers:\n"
            "  atlassian:\n"
            "    enabled: true\n"
            "agents:\n"
            "  coordinator:\n"
            "    prompt: test\n"
            "    tools: []\n"
        )
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert "atlassian" in result
        assert result["atlassian"]["enabled"] is True

    def test_loads_mcp_server_with_overrides(self, tmp_path, monkeypatch):
        """YAML overrides (transport, url) are preserved in the returned dict."""
        agents_yaml = tmp_path / "agents.yaml"
        agents_yaml.write_text(
            "mcp_servers:\n"
            "  atlassian:\n"
            "    enabled: true\n"
            "    transport: streamable_http\n"
            "    url: https://mcp.example.com\n"
            "agents:\n"
            "  coordinator:\n"
            "    prompt: test\n"
            "    tools: []\n"
        )
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert result["atlassian"]["transport"] == "streamable_http"
        assert result["atlassian"]["url"] == "https://mcp.example.com"

    def test_returns_empty_when_agents_yaml_missing(self, tmp_path, monkeypatch):
        """Missing agents.yaml returns {} rather than crashing."""
        monkeypatch.setattr(
            "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
            lambda: tmp_path,
        )
        result = load_mcp_config()
        assert result == {}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_config.py -v --no-cov`

Expected: FAIL — `ModuleNotFoundError: No module named 'autobots_devtools_shared_lib.dynagent.mcp'`

- [ ] **Step 4: Create the mcp package and config module**

Create `src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py`:

```python
# ABOUTME: Public API for the MCP integration layer.
# ABOUTME: Provides MCP client management, tool adapters, and server registration.

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport

__all__ = [
    "McpServerConfig",
    "McpTransport",
]
```

Create `src/autobots_devtools_shared_lib/dynagent/mcp/config.py`:

```python
# ABOUTME: MCP configuration types and YAML config loader.
# ABOUTME: Defines McpTransport enum, McpServerConfig dataclass, and load_mcp_config().

from dataclasses import dataclass
from enum import Enum
from typing import Any

import yaml

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import get_dynagent_settings

logger = get_logger(__name__)


class McpTransport(Enum):
    """Supported MCP transport protocols."""

    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


@dataclass
class McpServerConfig:
    """Configuration for connecting to an MCP server."""

    name: str
    transport: McpTransport

    # Stdio transport
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None

    # Streamable HTTP transport
    url: str | None = None

    # Auth — key in Dynagent state["mcp_auth"] dict holding the token
    auth_state_key: str | None = None


def get_config_dir():
    """Get the configuration directory from dynagent settings."""
    return get_dynagent_settings().dynagent_config_root_dir


def load_mcp_config() -> dict[str, dict[str, Any]]:
    """Read mcp_servers section from agents.yaml.

    Returns {} if the section is absent or agents.yaml doesn't exist.
    """
    config_path = get_config_dir() / "agents.yaml"
    try:
        with open(config_path) as f:  # noqa: PTH123
            data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.info("No agents.yaml found at %s — no MCP servers configured", config_path)
        return {}

    result = data.get("mcp_servers", {}) if data else {}
    if result:
        logger.info("Loaded MCP server config for: %s", list(result.keys()))
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_config.py -v --no-cov`

Expected: All 10 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py src/autobots_devtools_shared_lib/dynagent/mcp/config.py tests/unit/mcp/__init__.py tests/unit/mcp/test_config.py
git commit -m "feat: add MCP config types and YAML loader"
```

---

### Task 4: Create `McpServerRegistry`

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/registry.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/servers/__init__.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/servers/atlassian.py`
- Create: `tests/unit/mcp/test_registry.py`

- [ ] **Step 1: Write failing tests for the registry**

Create `tests/unit/mcp/test_registry.py`:

```python
# ABOUTME: Tests for McpServerRegistry singleton.
# ABOUTME: Validates bundled servers, usecase registration, override behavior, and reset.

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset registry before and after each test."""
    McpServerRegistry.reset()
    yield
    McpServerRegistry.reset()


class TestMcpServerRegistry:
    def test_instance_is_singleton(self):
        a = McpServerRegistry.instance()
        b = McpServerRegistry.instance()
        assert a is b

    def test_bundled_atlassian_is_available(self):
        reg = McpServerRegistry.instance()
        cfg = reg.get("atlassian")
        assert cfg.name == "atlassian"
        assert cfg.transport == McpTransport.STDIO
        assert cfg.command == "npx"

    def test_list_servers_includes_bundled(self):
        reg = McpServerRegistry.instance()
        assert "atlassian" in reg.list_servers()

    def test_get_unknown_server_raises(self):
        reg = McpServerRegistry.instance()
        with pytest.raises(KeyError, match="no_such_server"):
            reg.get("no_such_server")

    def test_register_usecase_server(self):
        reg = McpServerRegistry.instance()
        custom = McpServerConfig(
            name="custom",
            transport=McpTransport.STREAMABLE_HTTP,
            url="https://example.com",
        )
        reg.register(custom)
        assert reg.get("custom") is custom
        assert "custom" in reg.list_servers()

    def test_usecase_overrides_bundled(self):
        """Use-case registration with the same name overrides the bundled config."""
        reg = McpServerRegistry.instance()
        override = McpServerConfig(
            name="atlassian",
            transport=McpTransport.STREAMABLE_HTTP,
            url="https://override.example.com",
            auth_state_key="atlassian",
        )
        reg.register(override)
        cfg = reg.get("atlassian")
        assert cfg.transport == McpTransport.STREAMABLE_HTTP
        assert cfg.url == "https://override.example.com"

    def test_reset_clears_singleton(self):
        reg1 = McpServerRegistry.instance()
        McpServerRegistry.reset()
        reg2 = McpServerRegistry.instance()
        assert reg1 is not reg2

    def test_register_does_not_pollute_bundled(self):
        """Registering a usecase server must not modify the bundled dict."""
        reg = McpServerRegistry.instance()
        custom = McpServerConfig(name="custom", transport=McpTransport.STDIO, command="echo")
        reg.register(custom)
        # Bundled dict should not contain custom
        assert "custom" not in reg._bundled
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_registry.py -v --no-cov`

Expected: FAIL — `ModuleNotFoundError: No module named 'autobots_devtools_shared_lib.dynagent.mcp.registry'`

- [ ] **Step 3: Create bundled Atlassian server config**

Create `src/autobots_devtools_shared_lib/dynagent/mcp/servers/__init__.py`:

```python
# ABOUTME: Bundled MCP server definitions shipped with shared-lib.
# ABOUTME: Auto-registers all bundled servers into McpServerRegistry.

from autobots_devtools_shared_lib.dynagent.mcp.servers.atlassian import ATLASSIAN_MCP

BUNDLED_SERVERS = [ATLASSIAN_MCP]

__all__ = ["BUNDLED_SERVERS"]
```

Create `src/autobots_devtools_shared_lib/dynagent/mcp/servers/atlassian.py`:

```python
# ABOUTME: Bundled Atlassian MCP server configuration.
# ABOUTME: Provides Jira, Confluence, etc. via the Atlassian MCP server.

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport

ATLASSIAN_MCP = McpServerConfig(
    name="atlassian",
    transport=McpTransport.STDIO,
    command="npx",
    args=["@anthropic/atlassian-mcp-server"],
    auth_state_key="atlassian",
)
```

- [ ] **Step 4: Create the registry**

Create `src/autobots_devtools_shared_lib/dynagent/mcp/registry.py`:

```python
# ABOUTME: Singleton registry of MCP server definitions (bundled + usecase).
# ABOUTME: Use-case servers override bundled ones by name.

import threading

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig

logger = get_logger(__name__)

_instance: "McpServerRegistry | None" = None
_lock = threading.Lock()


class McpServerRegistry:
    """Holds MCP server definitions from bundled (shared-lib) and usecase sources."""

    def __init__(self) -> None:
        from autobots_devtools_shared_lib.dynagent.mcp.servers import BUNDLED_SERVERS

        self._bundled: dict[str, McpServerConfig] = {s.name: s for s in BUNDLED_SERVERS}
        self._usecase: dict[str, McpServerConfig] = {}
        logger.info("McpServerRegistry initialized with bundled: %s", list(self._bundled.keys()))

    @classmethod
    def instance(cls) -> "McpServerRegistry":
        """Return the singleton instance, creating it if needed."""
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton — for test isolation."""
        global _instance
        _instance = None

    def register(self, config: McpServerConfig) -> None:
        """Register a use-case MCP server. Overrides bundled by name."""
        self._usecase[config.name] = config
        logger.info("Registered usecase MCP server: %s", config.name)

    def get(self, name: str) -> McpServerConfig:
        """Lookup: usecase first, then bundled. Raises KeyError if not found."""
        if name in self._usecase:
            return self._usecase[name]
        if name in self._bundled:
            return self._bundled[name]
        msg = f"MCP server '{name}' not found. Available: {sorted(self.list_servers())}"
        raise KeyError(msg)

    def list_servers(self) -> list[str]:
        """All registered server names (bundled + usecase, deduplicated)."""
        return sorted({*self._bundled, *self._usecase})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_registry.py -v --no-cov`

Expected: All 8 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/mcp/registry.py src/autobots_devtools_shared_lib/dynagent/mcp/servers/__init__.py src/autobots_devtools_shared_lib/dynagent/mcp/servers/atlassian.py tests/unit/mcp/test_registry.py
git commit -m "feat: add McpServerRegistry with bundled Atlassian config"
```

---

### Task 5: Create `McpSessionManager`

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/session_manager.py`
- Create: `tests/unit/mcp/test_session_manager.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mcp/test_session_manager.py`:

```python
# ABOUTME: Tests for McpSessionManager — per-session MCP client lifecycle.
# ABOUTME: Uses mock MCP clients to test caching, cleanup, and error handling.

from unittest.mock import AsyncMock, patch

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager


@pytest.fixture(autouse=True)
def _reset():
    McpServerRegistry.reset()
    McpSessionManager.reset()
    yield
    McpSessionManager.reset()
    McpServerRegistry.reset()


@pytest.fixture
def stdio_server():
    """Register a test stdio server."""
    reg = McpServerRegistry.instance()
    cfg = McpServerConfig(
        name="test_server",
        transport=McpTransport.STDIO,
        command="echo",
        args=["hello"],
        auth_state_key="test_server",
    )
    reg.register(cfg)
    return cfg


class TestMcpSessionManager:
    async def test_instance_is_singleton(self):
        a = McpSessionManager.instance()
        b = McpSessionManager.instance()
        assert a is b

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_get_or_create_caches_connection(self, mock_create, stdio_server):
        mock_session = AsyncMock()
        mock_create.return_value = mock_session

        mgr = McpSessionManager.instance()
        first = await mgr.get_or_create("test_server", "session-1", "token-abc")
        second = await mgr.get_or_create("test_server", "session-1", "token-abc")

        assert first is second
        assert mock_create.call_count == 1

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_different_sessions_get_different_connections(self, mock_create, stdio_server):
        mock_create.side_effect = [AsyncMock(), AsyncMock()]

        mgr = McpSessionManager.instance()
        first = await mgr.get_or_create("test_server", "session-1", "token-a")
        second = await mgr.get_or_create("test_server", "session-2", "token-b")

        assert first is not second
        assert mock_create.call_count == 2

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_close_session_removes_connections(self, mock_create, stdio_server):
        mock_session = AsyncMock()
        mock_create.return_value = mock_session

        mgr = McpSessionManager.instance()
        await mgr.get_or_create("test_server", "session-1", "token-abc")
        await mgr.close_session("session-1")

        # Next call should create a new connection
        mock_create.return_value = AsyncMock()
        new_conn = await mgr.get_or_create("test_server", "session-1", "token-abc")
        assert new_conn is not mock_session

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.session_manager.McpSessionManager._create_connection"
    )
    async def test_close_all_clears_everything(self, mock_create, stdio_server):
        mock_create.side_effect = [AsyncMock(), AsyncMock()]

        mgr = McpSessionManager.instance()
        await mgr.get_or_create("test_server", "session-1", "token-a")
        await mgr.get_or_create("test_server", "session-2", "token-b")
        await mgr.close_all()

        assert len(mgr._connections) == 0

    async def test_get_or_create_unknown_server_raises(self):
        mgr = McpSessionManager.instance()
        with pytest.raises(KeyError, match="unknown_server"):
            await mgr.get_or_create("unknown_server", "session-1", None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_session_manager.py -v --no-cov`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement McpSessionManager**

Create `src/autobots_devtools_shared_lib/dynagent/mcp/session_manager.py`:

```python
# ABOUTME: Per-session MCP client connection manager.
# ABOUTME: Creates, caches, and tears down MCP connections keyed by (server_name, session_id).

from __future__ import annotations

import threading
from contextlib import AsyncExitStack
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry

logger = get_logger(__name__)

_instance: "McpSessionManager | None" = None
_lock = threading.Lock()


class _McpConnection:
    """Holds a ClientSession and its async exit stack for cleanup."""

    def __init__(self, session: ClientSession, exit_stack: AsyncExitStack) -> None:
        self.session = session
        self.exit_stack = exit_stack

    async def close(self) -> None:
        await self.exit_stack.aclose()


class McpSessionManager:
    """Manages per-session MCP client connections."""

    def __init__(self) -> None:
        self._connections: dict[tuple[str, str], _McpConnection] = {}

    @classmethod
    def instance(cls) -> McpSessionManager:
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    @classmethod
    def reset(cls) -> None:
        global _instance
        _instance = None

    async def get_or_create(
        self, server_name: str, session_id: str, auth_token: str | None
    ) -> ClientSession:
        """Return cached connection or create a new one."""
        key = (server_name, session_id)
        if key in self._connections:
            return self._connections[key].session

        # Validate server exists in registry
        config = McpServerRegistry.instance().get(server_name)
        conn = await self._create_connection(config, auth_token)
        self._connections[key] = conn
        logger.info("Created MCP connection: server=%s session=%s", server_name, session_id)
        return conn.session

    async def _create_connection(
        self, config: McpServerConfig, auth_token: str | None
    ) -> _McpConnection:
        """Create a new MCP client connection based on transport type."""
        stack = AsyncExitStack()

        if config.transport == McpTransport.STDIO:
            session = await self._connect_stdio(stack, config, auth_token)
        elif config.transport == McpTransport.STREAMABLE_HTTP:
            session = await self._connect_http(stack, config, auth_token)
        else:
            msg = f"Unsupported transport: {config.transport}"
            raise ValueError(msg)

        await session.initialize()
        return _McpConnection(session=session, exit_stack=stack)

    async def _connect_stdio(
        self, stack: AsyncExitStack, config: McpServerConfig, auth_token: str | None
    ) -> ClientSession:
        """Create a stdio MCP connection."""
        env = dict(config.env) if config.env else {}
        if auth_token and config.auth_state_key:
            env_key = f"{config.auth_state_key.upper()}_API_TOKEN"
            env[env_key] = auth_token

        params = StdioServerParameters(
            command=config.command or "",
            args=config.args or [],
            env=env if env else None,
        )
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        return session

    async def _connect_http(
        self, stack: AsyncExitStack, config: McpServerConfig, auth_token: str | None
    ) -> ClientSession:
        """Create a streamable HTTP MCP connection."""
        import httpx

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        http_client = httpx.AsyncClient(headers=headers) if headers else None
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client(config.url or "", http_client=http_client)
        )
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        return session

    async def close_session(self, session_id: str) -> None:
        """Tear down all MCP connections for a session."""
        keys_to_remove = [k for k in self._connections if k[1] == session_id]
        for key in keys_to_remove:
            conn = self._connections.pop(key)
            try:
                await conn.close()
            except Exception:
                logger.exception("Error closing MCP connection %s", key)
        if keys_to_remove:
            logger.info("Closed %d MCP connection(s) for session %s", len(keys_to_remove), session_id)

    async def close_all(self) -> None:
        """Shutdown hook — close all connections."""
        for key, conn in list(self._connections.items()):
            try:
                await conn.close()
            except Exception:
                logger.exception("Error closing MCP connection %s", key)
        self._connections.clear()
        logger.info("Closed all MCP connections")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_session_manager.py -v --no-cov`

Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/mcp/session_manager.py tests/unit/mcp/test_session_manager.py
git commit -m "feat: add McpSessionManager for per-session MCP connections"
```

---

### Task 6: Create `create_mcp_placeholder()` tool adapter

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/mcp/tool_adapter.py`
- Create: `tests/unit/mcp/test_tool_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mcp/test_tool_adapter.py`:

```python
# ABOUTME: Tests for MCP tool adapter — creates namespaced LangChain tool placeholders.
# ABOUTME: Validates naming, auth extraction, error messages, and MCP delegation.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager
from autobots_devtools_shared_lib.dynagent.mcp.tool_adapter import create_mcp_placeholder


@pytest.fixture(autouse=True)
def _reset():
    McpServerRegistry.reset()
    McpSessionManager.reset()
    yield
    McpSessionManager.reset()
    McpServerRegistry.reset()


@pytest.fixture
def _register_test_server():
    reg = McpServerRegistry.instance()
    reg.register(
        McpServerConfig(
            name="test_mcp",
            transport=McpTransport.STDIO,
            command="echo",
            auth_state_key="test_mcp",
        )
    )


class TestCreateMcpPlaceholder:
    def test_tool_name_is_namespaced(self):
        tool = create_mcp_placeholder("atlassian", "create_issue")
        assert tool.name == "atlassian.create_issue"

    def test_tool_has_description(self):
        tool = create_mcp_placeholder("atlassian", "create_issue")
        assert "atlassian.create_issue" in tool.description

    def test_tool_is_coroutine(self):
        tool = create_mcp_placeholder("atlassian", "create_issue")
        assert tool.coroutine is not None

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.tool_adapter.McpSessionManager"
    )
    async def test_invocation_reads_auth_from_mcp_auth(
        self, mock_mgr_cls, _register_test_server
    ):
        """Tool should read token from state['mcp_auth']['test_mcp']."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text="result-text", type="text")]
        mock_result.isError = False
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_mgr = MagicMock()
        mock_mgr.get_or_create = AsyncMock(return_value=mock_session)
        mock_mgr_cls.instance.return_value = mock_mgr

        tool = create_mcp_placeholder("test_mcp", "do_thing")

        state = {
            "messages": [],
            "session_id": "s1",
            "mcp_auth": {"test_mcp": "my-token"},
        }
        result = await tool.coroutine(state=state, tool_input={"key": "value"})

        mock_mgr.get_or_create.assert_called_once_with("test_mcp", "s1", "my-token")
        mock_session.call_tool.assert_called_once_with("do_thing", {"key": "value"})

    @patch(
        "autobots_devtools_shared_lib.dynagent.mcp.tool_adapter.McpSessionManager"
    )
    async def test_missing_auth_returns_friendly_error(self, mock_mgr_cls, _register_test_server):
        """When mcp_auth is missing, return an error message for the LLM."""
        tool = create_mcp_placeholder("test_mcp", "do_thing")

        state = {
            "messages": [],
            "session_id": "s1",
            # No mcp_auth
        }
        result = await tool.coroutine(state=state)

        assert "Authentication required" in result
        assert "test_mcp" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_tool_adapter.py -v --no-cov`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the tool adapter**

Create `src/autobots_devtools_shared_lib/dynagent/mcp/tool_adapter.py`:

```python
# ABOUTME: Wraps MCP tools as namespaced LangChain StructuredTools.
# ABOUTME: Creates lazy placeholder tools that connect to MCP servers on first invocation.

from __future__ import annotations

from typing import Any

from langchain.tools import StructuredTool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager

logger = get_logger(__name__)


def _extract_text(call_result: Any) -> str:
    """Extract text content from a CallToolResult."""
    if call_result.isError:
        parts = [c.text for c in call_result.content if hasattr(c, "text")]
        return f"MCP tool error: {' '.join(parts)}" if parts else "MCP tool returned an error"

    parts = []
    for content in call_result.content:
        if hasattr(content, "text"):
            parts.append(content.text)
    return "\n".join(parts) if parts else "MCP tool returned no text content"


def create_mcp_placeholder(server_name: str, tool_name: str) -> StructuredTool:
    """Create a LangChain tool placeholder that delegates to an MCP server on invocation.

    The tool is named '<server_name>.<tool_name>' (e.g., 'atlassian.create_issue').
    On first call, it lazily connects to the MCP server using the session's auth token.
    """
    full_name = f"{server_name}.{tool_name}"

    async def _invoke(state: dict[str, Any] | None = None, **kwargs: Any) -> str:
        state = state or {}
        session_id = state.get("session_id", "default")

        # Read auth token from state["mcp_auth"][auth_state_key]
        config = McpServerRegistry.instance().get(server_name)
        mcp_auth: dict[str, str] = state.get("mcp_auth", {})
        auth_token = mcp_auth.get(config.auth_state_key) if config.auth_state_key else None

        if config.auth_state_key and not auth_token:
            return (
                f"Authentication required for {server_name}. "
                f"Please provide your token (expected in mcp_auth['{config.auth_state_key}'])."
            )

        try:
            session = await McpSessionManager.instance().get_or_create(
                server_name, session_id, auth_token
            )
            # Extract tool_input from kwargs if passed, otherwise use remaining kwargs
            tool_input = kwargs.pop("tool_input", None) or kwargs or None
            result = await session.call_tool(tool_name, tool_input)
            return _extract_text(result)
        except Exception as e:
            logger.exception("MCP tool invocation failed: %s", full_name)
            return f"MCP tool '{full_name}' failed: {e}"

    return StructuredTool.from_function(
        coroutine=_invoke,
        func=lambda **kwargs: None,  # sync stub — async-only tool
        name=full_name,
        description=f"MCP tool: {full_name} (connects to {server_name} MCP server)",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_tool_adapter.py -v --no-cov`

Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/mcp/tool_adapter.py tests/unit/mcp/test_tool_adapter.py
git commit -m "feat: add MCP tool adapter with lazy placeholder pattern"
```

---

### Task 7: Integrate MCP into `get_tool_map()`

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py:192-217`
- Create: `tests/unit/mcp/test_get_tool_map_mcp.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mcp/test_get_tool_map_mcp.py`:

```python
# ABOUTME: Tests for MCP integration in get_tool_map().
# ABOUTME: Validates dotted tool names resolve to MCP placeholders, non-dotted unchanged.

import pytest

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    get_tool_map,
)
from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import _reset_usecase_tools


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    _reset_agent_config()
    _reset_usecase_tools()
    McpServerRegistry.reset()
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.mcp.config.get_config_dir",
        lambda: tmp_path,
    )
    yield
    _reset_agent_config()
    _reset_usecase_tools()
    McpServerRegistry.reset()


def _write_agents_yaml(tmp_path, content: str):
    (tmp_path / "agents.yaml").write_text(content)
    (tmp_path / "prompts").mkdir(exist_ok=True)
    (tmp_path / "prompts" / "test.md").write_text("You are a test agent.")


class TestGetToolMapMcp:
    def test_dotted_tool_name_creates_mcp_placeholder(self, tmp_path):
        """Tool name with '.' should resolve to an MCP placeholder."""
        McpServerRegistry.instance().register(
            McpServerConfig(name="atlas", transport=McpTransport.STDIO, command="echo")
        )
        _write_agents_yaml(
            tmp_path,
            "mcp_servers:\n  atlas:\n    enabled: true\n"
            "agents:\n  test_agent:\n    prompt: test\n    tools: [atlas.create_issue, handoff]\n",
        )
        tool_map = get_tool_map()
        names = [t.name for t in tool_map["test_agent"]]
        assert "atlas.create_issue" in names
        assert "handoff" in names

    def test_non_dotted_tools_still_resolve_normally(self, tmp_path):
        """Non-dotted tool names should resolve from the existing tool pool."""
        _write_agents_yaml(
            tmp_path,
            "agents:\n  test_agent:\n    prompt: test\n    tools: [handoff]\n",
        )
        tool_map = get_tool_map()
        names = [t.name for t in tool_map["test_agent"]]
        assert "handoff" in names

    def test_dotted_tool_unknown_server_raises(self, tmp_path):
        """Dotted tool referencing unregistered server should raise."""
        _write_agents_yaml(
            tmp_path,
            "agents:\n  test_agent:\n    prompt: test\n    tools: [unknown.do_thing]\n",
        )
        with pytest.raises(KeyError, match="unknown"):
            get_tool_map()

    def test_mixed_mcp_and_native_tools(self, tmp_path):
        """Agent with both MCP and native tools should resolve both."""
        McpServerRegistry.instance().register(
            McpServerConfig(name="jira", transport=McpTransport.STDIO, command="echo")
        )
        _write_agents_yaml(
            tmp_path,
            "mcp_servers:\n  jira:\n    enabled: true\n"
            "agents:\n  test_agent:\n    prompt: test\n    tools: [jira.search, handoff, get_agent_list]\n",
        )
        tool_map = get_tool_map()
        names = [t.name for t in tool_map["test_agent"]]
        assert "jira.search" in names
        assert "handoff" in names
        assert "get_agent_list" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_get_tool_map_mcp.py -v --no-cov`

Expected: FAIL — dotted tool names raise `ValueError: Unresolved tool` because the MCP branch doesn't exist yet.

- [ ] **Step 3: Add MCP branch to get_tool_map()**

In `src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py`, modify the `get_tool_map()` function. Replace the tool resolution loop (lines ~206-215):

**Current code:**
```python
        resolved: list[Any] = []
        for tool_name in cfg.tools:
            if tool_name in tool_by_name:
                resolved.append(tool_by_name[tool_name])
                logger.info(f"Agent '{name}': adding resolved tool '{tool_name}'")
            else:
                error_msg = f"Unresolved tool '{tool_name}' for agent '{name}'. Available tools: {sorted(tool_by_name.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)
```

**New code:**
```python
        resolved: list[Any] = []
        for tool_name in cfg.tools:
            if "." in tool_name:
                # Namespaced MCP tool — create a lazy placeholder
                server_name, mcp_tool_name = tool_name.split(".", 1)
                from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
                from autobots_devtools_shared_lib.dynagent.mcp.tool_adapter import (
                    create_mcp_placeholder,
                )

                McpServerRegistry.instance().get(server_name)  # validate server exists
                resolved.append(create_mcp_placeholder(server_name, mcp_tool_name))
                logger.info(f"Agent '{name}': adding MCP placeholder '{tool_name}'")
            elif tool_name in tool_by_name:
                resolved.append(tool_by_name[tool_name])
                logger.info(f"Agent '{name}': adding resolved tool '{tool_name}'")
            else:
                error_msg = f"Unresolved tool '{tool_name}' for agent '{name}'. Available tools: {sorted(tool_by_name.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/test_get_tool_map_mcp.py -v --no-cov`

Expected: All 4 tests pass.

- [ ] **Step 5: Run existing tool registry and agent config tests for regression**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/test_tool_registry.py tests/unit/test_agent_config_utils.py -v --no-cov`

Expected: All existing tests still pass (no dotted names in existing configs).

- [ ] **Step 6: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py tests/unit/mcp/test_get_tool_map_mcp.py
git commit -m "feat: integrate MCP placeholders into get_tool_map() for dotted tool names"
```

---

### Task 8: Wire up public API exports and `register_mcp_servers()`

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py`
- Modify: `src/autobots_devtools_shared_lib/dynagent/__init__.py`

- [ ] **Step 1: Update mcp package exports**

Update `src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py`:

```python
# ABOUTME: Public API for the MCP integration layer.
# ABOUTME: Provides MCP client management, tool adapters, and server registration.

from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry
from autobots_devtools_shared_lib.dynagent.mcp.session_manager import McpSessionManager
from autobots_devtools_shared_lib.dynagent.mcp.tool_adapter import create_mcp_placeholder


def register_mcp_servers(configs: list[McpServerConfig]) -> None:
    """Register use-case MCP server configs. Call once at startup before create_base_agent()."""
    registry = McpServerRegistry.instance()
    for config in configs:
        registry.register(config)


__all__ = [
    "McpServerConfig",
    "McpSessionManager",
    "McpServerRegistry",
    "McpTransport",
    "create_mcp_placeholder",
    "register_mcp_servers",
]
```

- [ ] **Step 2: Add MCP exports to dynagent __init__.py**

In `src/autobots_devtools_shared_lib/dynagent/__init__.py`, add the MCP imports:

Add these lines after the existing imports:

```python
from autobots_devtools_shared_lib.dynagent.mcp import (
    McpServerConfig,
    McpTransport,
    register_mcp_servers,
)
```

Add to `__all__`:

```python
    "McpServerConfig",
    "McpTransport",
    "register_mcp_servers",
```

- [ ] **Step 3: Verify imports work**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws && .venv/bin/python -c "from autobots_devtools_shared_lib.dynagent import McpServerConfig, McpTransport, register_mcp_servers; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/mcp/__init__.py src/autobots_devtools_shared_lib/dynagent/__init__.py
git commit -m "feat: export MCP public API from dynagent package"
```

---

### Task 9: Create example agents.yaml config

**Files:**
- Create: `configs/mcp-example/agents.yaml`
- Create: `configs/mcp-example/prompts/designer.md`

- [ ] **Step 1: Create example config directory**

```bash
mkdir -p /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib/configs/mcp-example/prompts
```

- [ ] **Step 2: Create example agents.yaml**

Create `configs/mcp-example/agents.yaml`:

```yaml
# Example agents.yaml showing MCP tool integration.
# This demonstrates how a use-case domain enables MCP servers
# and exposes their tools to specific agents.

mcp_servers:
  atlassian:
    enabled: true
    # Optional overrides (uncomment to customize):
    # transport: streamable_http
    # url: https://mcp.internal.company.com/atlassian

agents:
  designer:
    prompt: designer
    tools:
      - atlassian.create_issue
      - atlassian.search_issues
      - atlassian.get_issue
      - handoff
      - get_agent_list
    is_default: true
```

- [ ] **Step 3: Create example prompt**

Create `configs/mcp-example/prompts/designer.md`:

```markdown
You are a Designer agent. You help users manage their Jira issues.

You have access to Atlassian tools for creating, searching, and viewing Jira issues.
When a user asks you to create an issue, use the atlassian.create_issue tool.
When they want to find issues, use atlassian.search_issues.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
git add configs/mcp-example/
git commit -m "docs: add example agents.yaml showing MCP tool configuration"
```

---

### Task 10: Run full test suite and verify

**Files:** (no new files)

- [ ] **Step 1: Run all MCP unit tests**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/mcp/ -v --no-cov`

Expected: All MCP tests pass.

- [ ] **Step 2: Run full unit test suite**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m pytest tests/unit/ -v --no-cov`

Expected: All tests pass — no regressions.

- [ ] **Step 3: Run linter**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m ruff check src/autobots_devtools_shared_lib/dynagent/mcp/ tests/unit/mcp/`

Expected: No errors.

- [ ] **Step 4: Run type checker**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/pyright src/autobots_devtools_shared_lib/dynagent/mcp/`

Expected: No errors (or only pre-existing ones).

- [ ] **Step 5: Run formatter**

Run: `cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib && ../.venv/bin/python -m ruff format --check src/autobots_devtools_shared_lib/dynagent/mcp/ tests/unit/mcp/`

Expected: All files formatted correctly.

- [ ] **Step 6: Final commit if any formatting fixes needed**

```bash
cd /Users/shruthi/Projects/ws-autobots/autobots-multi-repo-ws/autobots-devtools-shared-lib
# Only if ruff format made changes:
git add -A
git commit -m "style: format MCP integration files"
```
