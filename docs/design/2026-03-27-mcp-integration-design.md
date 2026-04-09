# MCP Integration Layer — Design Spec

**Date:** 2026-03-27
**Status:** Draft
**Repo:** autobots-devtools-shared-lib
**Version target:** 0.5.0

## 1. Problem Statement

Dynagent agents need to interact with external services (Jira, Confluence, etc.) via the Model Context Protocol (MCP). Today there is no standard way to connect MCP servers to the Dynagent tool pipeline.

### Goals

1. **Generic MCP client layer** in shared-lib that any Dynagent agent can use.
2. **Bundled MCP integrations** (Atlassian first) shipped with shared-lib.
3. **Use-case extensibility** — domains can register their own MCP servers and override bundled ones.
4. **Minimal use-case code** — enabling an MCP server and exposing its tools is purely config.

### Non-Goals

- Chainlit UI changes for token collection (follow-up work).
- Wiring MCP tools into specific use-case agents like Designer (follow-up).
- SSE transport support (only stdio and streamable HTTP).

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ agents.yaml (use-case level)                            │
│                                                         │
│  mcp_servers:                                           │
│    atlassian:                                           │
│      enabled: true                                      │
│                                                         │
│  agents:                                                │
│    designer:                                            │
│      tools: [atlassian.create_issue, handoff]           │
└──────────────┬──────────────────────────────────────────┘
               │ startup
               ▼
┌──────────────────────────┐     ┌──────────────────────┐
│ agent_config_utils.py    │     │ McpServerRegistry     │
│ get_tool_map()           │────▶│ (bundled + usecase)   │
│                          │     └──────────────────────┘
│ "." in tool_name?        │
│  yes → MCP placeholder   │
│  no  → existing pool     │
└──────────────┬───────────┘
               │ runtime (first tool invocation)
               ▼
┌──────────────────────────┐     ┌──────────────────────┐
│ MCP Placeholder Tool     │     │ McpSessionManager     │
│                          │────▶│ (server, session_id)  │
│ reads auth_token from    │     │  → McpClient          │
│ Dynagent state           │     └──────────────────────┘
└──────────────────────────┘               │
                                           ▼
                                ┌──────────────────────┐
                                │ MCP Server            │
                                │ (stdio / HTTP)        │
                                └──────────────────────┘
```

## 3. Package Structure

New subpackage at `src/autobots_devtools_shared_lib/dynagent/mcp/`:

```
dynagent/mcp/
├── __init__.py              # Public API exports
├── config.py                # McpServerConfig, McpTransport enum
├── registry.py              # McpServerRegistry singleton
├── session_manager.py       # McpSessionManager — per-session connection lifecycle
├── tool_adapter.py          # MCP tool → namespaced LangChain tool wrapper
└── servers/                 # Bundled MCP server definitions
    ├── __init__.py
    └── atlassian.py         # Atlassian MCP config
```

## 4. Core Types

### 4.1 McpTransport

```python
class McpTransport(Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"
```

### 4.2 McpServerConfig

```python
@dataclass
class McpServerConfig:
    name: str                          # Server identifier, e.g. "atlassian"
    transport: McpTransport

    # Stdio transport
    command: str | None = None         # e.g. "npx"
    args: list[str] | None = None     # e.g. ["@anthropic/atlassian-mcp-server"]
    env: dict[str, str] | None = None # Additional env vars for subprocess

    # Streamable HTTP transport
    url: str | None = None            # e.g. "https://mcp.internal.company.com/atlassian"

    # Auth
    auth_state_key: str | None = None # Key in Dynagent state holding the token
```

`auth_state_key` is the bridge between Dynagent session state and MCP auth. The Chainlit UI stores the user's token at this key after first-time collection. The tool adapter reads it at invocation time.

## 5. MCP Server Registry

### 5.0 Auth Token Storage in Dynagent State

`Dynagent` is a `TypedDict` with three declared fields (`agent_name`, `session_id`, `user_name`). MCP auth tokens need a home. Rather than polluting the typed state with per-server keys, we add a single generic field:

```python
class Dynagent(AgentState):
    agent_name: NotRequired[str]
    session_id: NotRequired[str]
    user_name: NotRequired[str]
    mcp_auth: NotRequired[dict[str, str]]  # {server_name: token}
```

The tool adapter reads `runtime.state.get("mcp_auth", {}).get(config.auth_state_key)`. The Chainlit UI stores the token as `state["mcp_auth"]["atlassian"] = "<token>"`.

This keeps the state schema clean — one typed dict field for all MCP auth rather than arbitrary keys — and satisfies Pyright.

### 5.1 Registry

Singleton holding server definitions from two sources:

- **Bundled** — shipped with shared-lib in `mcp/servers/` (e.g., Atlassian).
- **Use-case** — registered at startup via `register_mcp_servers()`.

Use-case definitions override bundled ones by name (same pattern as `get_all_tools()` where usecase tools win on collision).

```python
class McpServerRegistry:
    _bundled: dict[str, McpServerConfig]
    _usecase: dict[str, McpServerConfig]

    @classmethod
    def instance(cls) -> "McpServerRegistry": ...

    def register(self, config: McpServerConfig) -> None:
        """Register a use-case MCP server."""

    def get(self, name: str) -> McpServerConfig:
        """Lookup: usecase first, then bundled. Raises KeyError if not found."""

    def list_servers(self) -> list[str]:
        """All registered server names."""
```

### 5.2 Bundled Atlassian Config

```python
# mcp/servers/atlassian.py
ATLASSIAN_MCP = McpServerConfig(
    name="atlassian",
    transport=McpTransport.STDIO,
    command="npx",
    args=["@anthropic/atlassian-mcp-server"],
    auth_state_key="atlassian",
)
```

### 5.3 Use-Case Registration

```python
# In a use-case's server.py (e.g., Designer)
from autobots_devtools_shared_lib.dynagent.mcp import register_mcp_servers

register_mcp_servers([my_custom_mcp_config])
```

### 5.4 agents.yaml Integration

A new top-level `mcp_servers` section enables servers for the domain:

```yaml
mcp_servers:
  atlassian:
    enabled: true
    # Optional overrides:
    # transport: streamable_http
    # url: https://mcp.internal.company.com/atlassian

agents:
  designer:
    tools: [atlassian.create_issue, atlassian.search_issues, handoff]
```

**Parsing:** A new `load_mcp_config()` function in `mcp/config.py` (not in `agent_config_utils.py`) reads the `mcp_servers` section from the same `agents.yaml` file. `load_agents_config()` is **not modified** — it continues to read only the `agents` section.

```python
# mcp/config.py
def load_mcp_config() -> dict[str, McpServerYamlEntry]:
    """Read mcp_servers section from agents.yaml. Returns {} if absent."""
    config_path = get_config_dir() / "agents.yaml"
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("mcp_servers", {})
```

**Initialization:** `load_mcp_config()` is called from `get_tool_map()` — the same function that resolves dotted tool names into MCP placeholders. This is the natural call site since `get_tool_map()` already needs to know which servers are enabled to validate dotted names. It runs before `AgentMeta` populates its `tool_map`. For each enabled server, it:

1. Looks up the bundled `McpServerConfig` by name from `McpServerRegistry`.
2. Applies any YAML overrides (transport, url, etc.) onto the bundled config.
3. If the server name is not bundled and not use-case-registered, raises `ValueError`.

This keeps `load_agents_config()` unchanged — no new return type, no broken callers. The MCP config is a parallel path through the same YAML file.

## 6. Session Manager

MCP connections are stateful and need per-session auth. `McpSessionManager` manages connection lifecycle keyed by `(server_name, session_id)`.

```python
class McpSessionManager:
    _connections: dict[tuple[str, str], McpClient]

    @classmethod
    def instance(cls) -> "McpSessionManager": ...

    async def get_or_create(
        self, server_name: str, session_id: str, auth_token: str | None
    ) -> McpClient:
        """Return existing connection or create a new one."""

    async def close_session(self, session_id: str) -> None:
        """Tear down all MCP connections for a session."""

    async def close_all(self) -> None:
        """Shutdown hook — close all connections."""
```

### 6.1 Connection Flow

1. Agent invokes `atlassian.create_issue` tool.
2. Tool adapter reads `session_id` and `state["mcp_auth"]["atlassian"]` from Dynagent state.
3. Calls `session_manager.get_or_create("atlassian", session_id, token)`.
4. If no connection exists:
   - Looks up `McpServerConfig` from registry.
   - **Stdio:** spawns subprocess with `command`/`args`, injects token via `env`.
   - **Streamable HTTP:** opens HTTP session to `url` with token in auth header.
5. Returns the MCP client; tool adapter calls the MCP tool through it.

### 6.2 Connection Properties

- **Lazy:** No connections at startup. Created on first tool invocation per session.
- **Cached:** Subsequent calls to the same server within a session reuse the connection.
- **Cleanup:** `close_session(session_id)` kills stdio subprocesses and closes HTTP sessions. The **use-case layer** (not shared-lib) is responsible for calling this from Chainlit's `on_chat_end` or equivalent lifecycle hook. Shared-lib provides the method; the call site is in use-case code.

## 7. Tool Adapter

Wraps MCP tools as namespaced LangChain tools that integrate with the existing Dynagent pipeline.

### 7.1 The Placeholder Pattern

**Problem:** Dynagent resolves all tools at startup via `get_tool_map()`, but MCP tool discovery requires a live connection, which requires a session token that doesn't exist at startup.

**Solution:** At startup, MCP tools declared in `agents.yaml` are registered as thin placeholder tools. On first invocation, the placeholder lazily establishes the connection, discovers the real tool, delegates the call, and caches the schema.

```python
def create_mcp_placeholder(server_name: str, tool_name: str) -> StructuredTool:
    full_name = f"{server_name}.{tool_name}"

    async def _lazy_invoke(runtime: ToolRuntime[None, Dynagent], **kwargs) -> str:
        session_id = runtime.state.get("session_id", "default")
        config = McpServerRegistry.instance().get(server_name)
        mcp_auth = runtime.state.get("mcp_auth", {})
        auth_token = mcp_auth.get(config.auth_state_key) if config.auth_state_key else None
        client = await McpSessionManager.instance().get_or_create(
            server_name, session_id, auth_token
        )
        return await client.call_tool(tool_name, kwargs)

    return StructuredTool.from_function(
        func=_lazy_invoke,
        name=full_name,
        description=f"MCP tool: {full_name} (resolves on first use)",
    )

# Note: After the first successful connection, the placeholder caches the real
# tool's description and input schema from client.list_tools(). Subsequent
# invocations benefit from the richer metadata for LLM tool selection.
```

### 7.2 Integration Point — get_tool_map()

The **only change to existing code** is a small branch in `agent_config_utils.py`:

```python
# In get_tool_map()
for tool_name in cfg.tools:
    if "." in tool_name:  # Namespaced → MCP tool
        server_name, mcp_tool_name = tool_name.split(".", 1)
        resolved.append(create_mcp_placeholder(server_name, mcp_tool_name))
    elif tool_name in tool_by_name:
        resolved.append(tool_by_name[tool_name])
    else:
        raise ValueError(...)
```

No changes to middleware, AgentMeta, base_agent, or tool_registry.

## 8. Auth Flow

```
User logs in (GitHub via Chainlit)
        │
        ▼
First MCP tool invocation
        │
        ▼
Chainlit UI prompts for Atlassian token
        │
        ▼
Token stored in Dynagent state: state["mcp_auth"]["atlassian"] = "<token>"
        │
        ▼
Tool adapter reads state["mcp_auth"][config.auth_state_key]
        │
        ▼
Passed to McpSessionManager.get_or_create()
        │
        ▼
Injected into MCP transport:
  - Stdio: env var (e.g. ATLASSIAN_API_TOKEN=<token>)
  - HTTP: Authorization header
```

## 9. Error Handling

| Scenario | Behavior |
|----------|----------|
| Auth token missing at invocation | Return LLM-friendly error: "Authentication required for {server}. Please provide your token." Agent communicates to user via Chainlit. |
| MCP server unreachable (stdio spawn fails) | Catch `OSError`, return tool error to LLM. No retries — LLM decides. |
| MCP server unreachable (HTTP timeout) | Catch timeout, return tool error to LLM. |
| Declared tool not found on MCP server | `client.list_tools()` on first use. If tool missing, raise `ValueError` with available tools listed. |
| Session cleanup race (in-flight call during close) | `close_session()` sets closed flag. In-flight calls fail gracefully. |
| Use-case override conflict | `McpServerRegistry.get()` checks usecase dict first, bundled second. |

## 10. Configuration Example

### Shared-lib bundled (no user action needed):

```python
# Already registered in mcp/servers/atlassian.py
ATLASSIAN_MCP = McpServerConfig(
    name="atlassian",
    transport=McpTransport.STDIO,
    command="npx",
    args=["@anthropic/atlassian-mcp-server"],
    auth_state_key="atlassian",
)
```

### Use-case agents.yaml (Designer domain):

```yaml
mcp_servers:
  atlassian:
    enabled: true

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

### Use-case custom MCP (not in shared-lib):

```python
# In use-case server.py
from autobots_devtools_shared_lib.dynagent.mcp import McpServerConfig, McpTransport, register_mcp_servers

custom_mcp = McpServerConfig(
    name="internal_api",
    transport=McpTransport.STREAMABLE_HTTP,
    url="https://mcp.internal.company.com/api",
    auth_state_key="internal_api",
)
register_mcp_servers([custom_mcp])
```

## 11. Testing Strategy

### Unit Tests (no real MCP servers)

| Component | What's tested |
|-----------|---------------|
| `McpServerRegistry` | Register, override, lookup, list. Usecase-wins-on-collision. |
| `McpSessionManager` | get_or_create caching, close_session cleanup, close_all. Mock MCP clients. |
| `McpToolAdapter` / placeholders | Namespacing, auth token extraction from state, delegation to `client.call_tool()`, error when tool not found. |
| `get_tool_map()` change | Dotted names → MCP placeholders, non-dotted → existing pool, mixed lists work. |
| Error paths | Missing auth token returns LLM-friendly error, unreachable server handled gracefully. |

### Integration Tests (skipped in CI)

- Spin up a lightweight test MCP server (stdio) exposing dummy tools.
- Full flow: config → registry → session → discover → invoke → response.
- Marker: `@pytest.mark.integration`, skip if test MCP server binary not available.

### Existing Tests

No changes needed. The `get_tool_map()` branch only triggers for dotted tool names, which no existing config uses.

## 12. Dependencies

New runtime dependency:

- `mcp` — official MCP Python SDK (provides client, transports, types)

## 13. Deliverables

1. `dynagent/mcp/` subpackage (config, registry, session_manager, tool_adapter)
2. Bundled Atlassian MCP server definition
3. `get_tool_map()` integration (single branch addition)
4. Example `agents.yaml` showing MCP tool usage
5. Unit tests for all new components
6. Integration test with dummy MCP server
7. Public API exports from `dynagent/__init__.py`
