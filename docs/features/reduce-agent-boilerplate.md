# Reduce Boilerplate for Adding New Bro Agents

## Problem

Currently, adding a new agent requires code changes in multiple places:
1. Add to `BroAgentList` Literal type
2. Add to `get_bro_agent_list()` function
3. Add configuration to `build_step_config()` dictionary
4. Update tests with new agent name

**Goal**: Make adding agents config-only - no code changes required.

---

## Solution: Config-Driven Agent System

The `agents.yaml` configuration already exists with all necessary information, but `bro.py` duplicates it in hardcoded Python. We'll refactor to use the config as the single source of truth.

---

## Changes

### 1. Create Tool Registry

**File**: `src/bro_chat/agents/bro_tools_registry.py` (new)

Create a mapping from tool names (strings in YAML) to actual tool objects:

```python
def create_tool_registry(store: DocumentStore) -> dict[str, Any]:
    """Create registry mapping tool names to tool objects."""
    tools = create_bro_tools(store)

    return {
        "handoff": tools["handoff"],
        "set_document_context": tools["set_document_context"],
        "get_document_status": tools["get_document_status"],
        "list_documents": tools["list_documents"],
        "create_document": tools["create_document"],
        "update_section": tools["update_section"],
        "set_section_status": tools["set_section_status"],
        "create_entity": tools["create_entity"],
        "list_entities": tools["list_entities"],
        "delete_entity": tools["delete_entity"],
        "export_markdown": tools["export_markdown"],
    }
```

**Why**: Decouples tool names in config from tool implementation.

---

### 2. Refactor build_step_config()

**File**: `src/bro_chat/agents/bro.py`

**Current** (90+ lines, hardcoded):
```python
def build_step_config(tools: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coordinator_tools = [tools["handoff"], tools["get_document_status"], ...]
    section_tools = [tools["handoff"], tools["update_section"], ...]

    return {
        "coordinator": {
            "prompt": load_prompt("vision-agent/coordinator"),
            "tools": coordinator_tools,
            "requires": [],
        },
        "preface_agent": {
            "prompt": load_prompt("vision-agent/01-preface"),
            "tools": section_tools,
            "requires": [],
        },
        # ... repeat for each agent
    }
```

**New** (config-driven):
```python
def build_step_config(
    tool_registry: dict[str, Any],
    config_dir: Path = Path("configs/vision-agent"),
) -> dict[str, dict[str, Any]]:
    """Build step config from agents.yaml configuration."""
    from autobots_agents_bro.config.section_config import load_agents_config

    agents_config = load_agents_config(config_dir)
    step_config = {}

    for agent_id, agent_cfg in agents_config.items():
        # Map tool names to tool objects
        tool_objects = [tool_registry[name] for name in agent_cfg.tools]

        step_config[agent_id] = {
            "prompt": load_prompt(agent_cfg.prompt),
            "tools": tool_objects,
            "requires": [],  # Could also come from config if needed
        }

    return step_config
```

**Benefits**:
- Single source of truth (agents.yaml)
- Adding agent = just edit YAML
- No code changes needed

---

### 3. Make Agent List Dynamic

**File**: `src/bro_chat/agents/bro.py`

**Option A: Remove BroAgentList entirely**

Replace the Literal type with string validation:
```python
# Remove BroAgentList = Literal[...]

def get_bro_agent_list(
    config_dir: Path = Path("configs/vision-agent")
) -> list[str]:
    """Return list of available bro agent names from config."""
    from autobots_agents_bro.config.section_config import load_agents_config

    agents_config = load_agents_config(config_dir)
    return list(agents_config.keys())
```

Update type hints:
```python
# Before
def handoff(..., next_agent: BroAgentList) -> Command:

# After
def handoff(..., next_agent: str) -> Command:
    # Add runtime validation
    valid_agents = get_bro_agent_list()
    if next_agent not in valid_agents:
        raise ValueError(f"Invalid agent: {next_agent}")
```

**Option B: Generate BroAgentList dynamically** (more complex)

```python
def _get_agent_literal():
    """Generate Literal type from config at import time."""
    from autobots_agents_bro.config.section_config import load_agents_config

    agents = load_agents_config(Path("configs/vision-agent"))
    agent_names = tuple(agents.keys())
    return Literal[agent_names]  # Dynamic literal

BroAgentList = _get_agent_literal()
```

**Recommendation**: Option A (simpler, still type-safe with runtime validation)

---

### 4. Update BroAgentState

**File**: `src/bro_chat/agents/bro.py`

```python
class BroAgentState(AgentState):
    """State for the bro agent workflow."""

    current_step: NotRequired[str]  # Changed from BroAgentList
    component: NotRequired[str]
    version: NotRequired[str]
    entity_name: NotRequired[str]
```

---

### 5. Update create_bro_agent()

**File**: `src/bro_chat/agents/bro.py`

```python
def create_bro_agent(
    store: DocumentStore | None = None,
    checkpointer: Any = None,
    base_path: Path | str = "vision-docs",
    config_dir: Path = Path("configs/vision-agent"),
):
    """Create the bro agent with step-based middleware."""
    if store is None:
        store = DocumentStore(base_path=base_path)

    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Create tool registry
    tool_registry = create_tool_registry(store)

    # Build step config from agents.yaml
    step_config = build_step_config(tool_registry, config_dir)

    # Collect all tools
    all_tools = []
    for config in step_config.values():
        all_tools.extend(config["tools"])

    # ... rest of agent creation
```

---

### 6. Update Tests

**File**: `tests/integration/test_bro_agent.py`

**Before** (hardcoded):
```python
def test_includes_mvp_agents(self) -> None:
    agents = get_bro_agent_list()
    assert "preface_agent" in agents
    assert "getting_started_agent" in agents
    assert "features_agent" in agents
    assert "entity_agent" in agents
```

**After** (config-driven):
```python
def test_includes_agents_from_config(self, tmp_path: Path) -> None:
    """Agent list should match agents.yaml config."""
    agents = get_bro_agent_list()

    # Load config directly to verify consistency
    from autobots_agents_bro.config.section_config import load_agents_config
    expected = load_agents_config(Path("configs/vision-agent"))

    assert set(agents) == set(expected.keys())
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/bro_chat/agents/bro.py` | Refactor build_step_config(), update type hints, make agent list dynamic |
| `src/bro_chat/agents/bro_tools_registry.py` | **New file** - Create tool registry |
| `tests/integration/test_bro_agent.py` | Update tests to be config-driven |
| `configs/vision-agent/agents.yaml` | No changes (already correct structure) |

---

## Migration Path

### Phase 1: Create Tool Registry (Non-Breaking)
1. Create `bro_tools_registry.py`
2. Add tests for tool registry
3. No changes to existing code yet

### Phase 2: Refactor build_step_config() (Non-Breaking)
1. Update `build_step_config()` to accept tool registry and load from config
2. Update `get_step_config()` to use new approach
3. Tests still pass (same behavior, different implementation)

### Phase 3: Update Type Hints (Breaking Changes)
1. Replace `BroAgentList` with `str` in type hints
2. Add runtime validation
3. Update tests
4. Update state class

### Phase 4: Documentation
1. Update CLAUDE.md with new approach
2. Document how to add new agents (just YAML + prompt file)

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Adding Agent** | 4 code changes + config | 1 config change only |
| **Type Safety** | Compile-time Literal | Runtime validation |
| **Maintainability** | Duplication (YAML + code) | Single source of truth |
| **Testing** | Hardcoded agent names | Config-driven |
| **Extensibility** | Modify Python code | Edit YAML file |

---

## Verification

After implementation:

1. **Run all existing tests** - should pass without changes:
   ```bash
   uv run pytest tests/ -v
   ```

2. **Test adding a new agent** by only editing config:
   ```yaml
   # Add to configs/vision-agent/agents.yaml
   business_processes_agent:
     section: "03-02"
     prompt: "vision-agent/03-02-business-processes"
     tools:
       - "handoff"
       - "update_section"
   ```
   Create prompt file, verify agent appears in `get_bro_agent_list()`, and works without code changes.

3. **Verify type checking**:
   ```bash
   uv run pyright src/bro_chat/
   ```

4. **Verify linting**:
   ```bash
   uv run ruff check src/bro_chat/
   ```

---

## Future Enhancements

Once this refactor is complete, further config-driven features become easy:

- **Dynamic requires**: Add `requires: ["component", "version"]` to agents.yaml
- **Agent metadata**: Add descriptions, categories, tags in YAML
- **Tool validation**: Validate tool names in YAML against registry at startup
- **Hot reload**: Reload agents.yaml without restarting
