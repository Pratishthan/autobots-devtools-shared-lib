# CopilotKit v2 Backend Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dynagent graph emit CopilotKit v2-compatible events and serve it with copilotkit's agent wrapper, without changing any non-UI invocation path.

**Architecture:** Add an opt-in `copilotkit=True` flag to `create_base_agent` that appends `copilotkit.CopilotKitMiddleware()` to the existing `langchain.agents.create_agent` middleware stack. Switch `copilotkit_server.py` from `ag_ui_langgraph.LangGraphAgent` to `copilotkit.LangGraphAGUIAgent`, derive the graph id from the configured default agent, and log it so the (later) v2 frontend route can match. The `copilotkit` Python package is added to the existing `[copilotkit-ui]` optional extra and imported lazily so the core library stays import-light.

**Tech Stack:** Python 3.12+, `langchain.agents.create_agent`, LangGraph, FastAPI, `copilotkit==0.1.94` (Python), `ag-ui-langgraph`, pytest.

## Global Constraints

- This is **sub-project 1 of 6** in `docs/superpowers/specs/2026-06-24-copilotkit-v2-alignment-design.md`. No `ui/` frontend changes, no Atlas-mock removal, no `StateStreamingMiddleware`, no threads/tool-rendering/suggestions/MCP — those are later sub-projects.
- `create_base_agent()` with no args (or `copilotkit=False`) MUST produce a byte-for-byte identical middleware stack to today — batch, CLI, and all domains must be unaffected.
- The `copilotkit` package MUST be imported **lazily** (inside the function that needs it), never at module top level — it is an optional extra.
- Code style: Ruff, line-length 100, double quotes. Python 3.12+. Pyright basic mode.
- Commit from **inside the `autobots-devtools-shared-lib` repo** (not the workspace root). End every commit message with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Pin: add `copilotkit>=0.1.94` (matches the reference's `copilotkit==0.1.94`).

### Prerequisite (pre-existing, not introduced by this plan)

Three tests in `tests/unit/test_invocation_utils.py` (`test_adds_langfuse_callback_when_tracing_enabled`, `test_preserves_existing_callbacks`, `test_adds_langfuse_callback_when_tracing_enabled_async`) are **already failing** on `main`/this branch and will block the pre-commit `pytest` hook. Before starting, either fix them (separate concern) or run plan commits with `git commit --no-verify` and address them independently. Each task below runs its **own** tests directly (`make test-one ...`) to verify behavior regardless.

---

### Task 1: Add `copilotkit` to the `[copilotkit-ui]` optional extra

**Files:**
- Modify: `pyproject.toml:41-44`

**Interfaces:**
- Consumes: nothing.
- Produces: the `copilotkit` package (and its transitive `ag-ui-langgraph[fastapi]`) importable in the shared venv. Tasks 2 and 3 rely on `from copilotkit import CopilotKitMiddleware` and `from copilotkit import LangGraphAGUIAgent`.

- [ ] **Step 1: Add the dependency to the extra**

Edit `pyproject.toml` so the extra reads:

```toml
[project.optional-dependencies]
copilotkit-ui = [
    "ag-ui-langgraph>=0.0.42; python_version < '3.15'",
    "copilotkit>=0.1.94; python_version < '3.15'",
]
```

- [ ] **Step 2: Install the extra into the shared venv**

Run:
```bash
source ../.venv/bin/activate && pip install -e ".[copilotkit-ui]"
```
Expected: install completes; `copilotkit-0.1.94` (or newer) and `ag-ui-langgraph` appear in the output / are already satisfied.

- [ ] **Step 3: Verify the imports resolve**

Run:
```bash
source ../.venv/bin/activate && python -c "from copilotkit import CopilotKitMiddleware, LangGraphAGUIAgent; print('ok')"
```
Expected: prints `ok` with no traceback.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build(ui): add copilotkit python package to copilotkit-ui extra

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add opt-in `copilotkit` flag to `create_base_agent`

Extract the middleware-list construction into a focused, pure helper so it can be unit-tested without building a real model or loading domain config, then wire a new `copilotkit` flag through it.

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/agents/base_agent.py`
- Test: `tests/unit/test_base_agent.py` (create)

**Interfaces:**
- Consumes: `inject_agent_sync`, `inject_agent_async` (existing module-level middleware instances); `SummarizationMiddleware`; `from copilotkit import CopilotKitMiddleware` (lazy, from Task 1).
- Produces:
  - `build_middleware_stack(model: Any, *, sync_mode: bool = False, copilotkit: bool = False) -> list[AgentMiddleware[Any, Any]]` — returns `[inject, SummarizationMiddleware]`, plus a trailing `CopilotKitMiddleware()` when `copilotkit=True`.
  - `create_base_agent(..., copilotkit: bool = False)` — Task 3 calls this with `copilotkit=True`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_base_agent.py`:

```python
# ABOUTME: Unit tests for the dynagent base-agent middleware assembly.
# ABOUTME: Verifies the opt-in copilotkit flag is additive and default-safe.

from unittest.mock import MagicMock

import pytest


def test_build_middleware_stack_default_has_no_copilotkit():
    """Default stack is inject + summarization, with no CopilotKit middleware."""
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    stack = build_middleware_stack(MagicMock(name="model"))

    assert len(stack) == 2
    assert not any(type(m).__name__ == "CopilotKitMiddleware" for m in stack)


def test_build_middleware_stack_sync_mode_default_unchanged():
    """sync_mode swaps the inject middleware but stays copilotkit-free by default."""
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    stack = build_middleware_stack(MagicMock(name="model"), sync_mode=True)

    assert len(stack) == 2
    assert not any(type(m).__name__ == "CopilotKitMiddleware" for m in stack)


def test_build_middleware_stack_copilotkit_appends_middleware():
    """copilotkit=True appends exactly one trailing CopilotKitMiddleware."""
    pytest.importorskip("copilotkit")
    from autobots_devtools_shared_lib.dynagent.agents.base_agent import build_middleware_stack

    stack = build_middleware_stack(MagicMock(name="model"), copilotkit=True)

    assert len(stack) == 3
    assert type(stack[-1]).__name__ == "CopilotKitMiddleware"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
make test-one TEST=tests/unit/test_base_agent.py
```
Expected: FAIL — `ImportError: cannot import name 'build_middleware_stack'`.

- [ ] **Step 3: Implement the helper and thread the flag**

In `src/autobots_devtools_shared_lib/dynagent/agents/base_agent.py`, add the helper above `create_base_agent`:

```python
def build_middleware_stack(
    model: Any,
    *,
    sync_mode: bool = False,
    copilotkit: bool = False,
) -> list[AgentMiddleware[Any, Any]]:
    """Assemble the dynagent middleware list.

    The base stack (agent-injection + summarization) is identical to the
    historical inline list. When ``copilotkit`` is True, a trailing
    ``CopilotKitMiddleware`` is appended so the graph emits CopilotKit/AG-UI
    events. ``copilotkit`` is an optional extra, so it is imported lazily.
    """
    inject = inject_agent_sync if sync_mode else inject_agent_async
    stack: list[AgentMiddleware[Any, Any]] = [
        inject,
        SummarizationMiddleware(
            model=model,
            trigger=("fraction", 0.6),
            keep=("messages", 20),
        ),
    ]
    if copilotkit:
        from copilotkit import CopilotKitMiddleware

        stack.append(CopilotKitMiddleware())
    return stack
```

Then add the `copilotkit` parameter to `create_base_agent` and replace its inline `middleware=cast(...)` argument with a call to the helper. The signature becomes:

```python
def create_base_agent(
    checkpointer: Any = None,
    sync_mode: bool = False,
    initial_agent_name: str | None = None,
    state_schema: type[AgentState[ResponseT]] = Dynagent,
    copilotkit: bool = False,
) -> CompiledStateGraph:
```

and the `create_agent(...)` call's `middleware=` argument becomes:

```python
        middleware=cast(
            "list[AgentMiddleware[Any, Any]]",
            build_middleware_stack(model, sync_mode=sync_mode, copilotkit=copilotkit),
        ),
```

Update the docstring's Args section to document `copilotkit: When True, append CopilotKitMiddleware so the graph emits CopilotKit/AG-UI events (used by the CopilotKit UI server). Default False leaves all other call paths unchanged.`

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
make test-one TEST=tests/unit/test_base_agent.py
```
Expected: PASS (3 passed).

- [ ] **Step 5: Lint and type-check the changed files**

Run:
```bash
make lint && make type-check
```
Expected: no new errors in `base_agent.py` or `tests/unit/test_base_agent.py`.

- [ ] **Step 6: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/base_agent.py tests/unit/test_base_agent.py
git commit -m "feat(dynagent): opt-in copilotkit middleware in create_base_agent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Serve with copilotkit's `LangGraphAGUIAgent` and a derived graph id

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`
- Test: `tests/unit/test_copilotkit_server.py:1-45` (extend)

**Interfaces:**
- Consumes: `create_base_agent(checkpointer=..., copilotkit=True)` (Task 2); `get_default_agent()` (`-> str | None`, existing in `agent_config_utils`); `from copilotkit import LangGraphAGUIAgent` (Task 1); `from ag_ui_langgraph import add_langgraph_fastapi_endpoint`.
- Produces: `create_copilotkit_app(agent_name: str | None = None, path: str = "/agent") -> FastAPI` — when `agent_name` is None it derives `get_default_agent() or "dynagent"`; mounts a copilotkit `LangGraphAGUIAgent` at `path`; logs the derived graph id.

- [ ] **Step 1: Write the failing tests**

Replace the body of `tests/unit/test_copilotkit_server.py` with (keeps the two existing route-mount assertions, adds derivation + copilotkit-flag coverage):

```python
# ABOUTME: Smoke test for the generic CopilotKit/AG-UI FastAPI app factory.
# ABOUTME: Confirms create_copilotkit_app builds and mounts the AG-UI route.

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("copilotkit")


@pytest.fixture
def mock_graph():
    """A stand-in compiled graph whose .with_config returns itself."""
    graph = MagicMock(name="compiled_graph")
    graph.with_config.return_value = graph
    return graph


@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_create_copilotkit_app_mounts_agui_route(mock_create_base_agent, mock_graph):
    """The factory returns a FastAPI app with the AG-UI route registered."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph

    app = create_copilotkit_app(agent_name="coordinator", path="/agent")

    mock_create_base_agent.assert_called_once()
    paths = {route.path for route in app.routes}
    assert "/agent" in paths


@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_create_copilotkit_app_default_args(mock_create_base_agent, mock_graph):
    """Defaults mount the derived agent at /agent."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph

    app = create_copilotkit_app()

    paths = {route.path for route in app.routes}
    assert "/agent" in paths


@patch("ag_ui_langgraph.add_langgraph_fastapi_endpoint")
@patch("copilotkit.LangGraphAGUIAgent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.get_default_agent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_builds_copilotkit_graph_and_derives_name(
    mock_create_base_agent, mock_get_default_agent, mock_agui_agent, mock_add_endpoint, mock_graph
):
    """When agent_name is omitted, the graph id is derived and copilotkit=True is passed."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph
    mock_get_default_agent.return_value = "myagent"

    create_copilotkit_app()

    # create_base_agent was asked for the CopilotKit-flavored graph.
    assert mock_create_base_agent.call_args.kwargs.get("copilotkit") is True
    # The AG-UI agent is named after the derived default agent.
    assert mock_agui_agent.call_args.kwargs.get("name") == "myagent"


@patch("ag_ui_langgraph.add_langgraph_fastapi_endpoint")
@patch("copilotkit.LangGraphAGUIAgent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.get_default_agent")
@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_falls_back_to_dynagent_when_no_default(
    mock_create_base_agent, mock_get_default_agent, mock_agui_agent, mock_add_endpoint, mock_graph
):
    """With no configured default agent, the graph id falls back to 'dynagent'."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph
    mock_get_default_agent.return_value = None

    create_copilotkit_app()

    assert mock_agui_agent.call_args.kwargs.get("name") == "dynagent"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
make test-one TEST=tests/unit/test_copilotkit_server.py
```
Expected: FAIL — the two new tests fail because `get_default_agent` is not importable from `copilotkit_server`, and `create_base_agent` is not called with `copilotkit=True`.

- [ ] **Step 3: Update the server**

In `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`:

Add this import near the other top-level imports (so it is patchable as `copilotkit_server.get_default_agent`):

```python
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
```

Replace the body of `create_copilotkit_app` so it derives the id, passes `copilotkit=True`, uses copilotkit's agent class, and logs the id. The new function:

```python
def create_copilotkit_app(agent_name: str | None = None, path: str = "/agent") -> FastAPI:
    """Build a FastAPI app that serves a dynagent graph over the AG-UI protocol."""
    from ag_ui_langgraph import add_langgraph_fastapi_endpoint
    from copilotkit import LangGraphAGUIAgent

    # Derive the graph id from the configured default agent so the v2 frontend
    # route can target it. The operator should set the frontend's graphId to the
    # value logged below.
    graph_id = agent_name or get_default_agent() or "dynagent"

    graph = create_base_agent(  # pyright: ignore[reportCallIssue]
        checkpointer=InMemorySaver(),
        copilotkit=True,
    )

    langfuse_handler = get_langfuse_handler()
    if langfuse_handler is not None:
        graph = graph.with_config({"callbacks": [langfuse_handler], "recursion_limit": 50})
    else:
        graph = graph.with_config({"recursion_limit": 50})

    agent = LangGraphAGUIAgent(
        name=graph_id,
        description="Dynagent multi-agent coordinator served over AG-UI.",
        graph=graph,
    )

    app = FastAPI(title=f"Dynagent AG-UI ({graph_id})")

    # ── CORS: the React UI calls this server directly (no Next.js proxy) ──────
    # allow_credentials=True is required because the UI sends credentials:"include";
    # that forbids a wildcard origin, so list exact origins instead of "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    add_langgraph_fastapi_endpoint(app, agent, path)

    logger.info(
        f"Mounted CopilotKit AG-UI agent graphId='{graph_id}' at '{path}' "
        f"· set the frontend graphId to '{graph_id}' · CORS origins={ALLOWED_ORIGINS}"
    )
    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
make test-one TEST=tests/unit/test_copilotkit_server.py
```
Expected: PASS (4 passed).

- [ ] **Step 5: Lint and type-check**

Run:
```bash
make lint && make type-check
```
Expected: no new errors in `copilotkit_server.py` or its test.

- [ ] **Step 6: Smoke-test the server boots and mounts the route**

Run:
```bash
source ../.venv/bin/activate && python -c "
from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app
app = create_copilotkit_app()
print('routes:', sorted({r.path for r in app.routes}))
"
```
Expected: output includes `/agent` in the printed routes, and a log line reporting the derived `graphId` with no traceback. (Requires `DYNAGENT_CONFIG_ROOT_DIR` set for a domain, per repo CLAUDE.md; if model/config init fails for environment reasons, note it — the unit tests in Step 4 are the authoritative gate for this task.)

- [ ] **Step 7: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py tests/unit/test_copilotkit_server.py
git commit -m "feat(ui): serve dynagent via copilotkit LangGraphAGUIAgent

Switch the AG-UI server to copilotkit's LangGraphAGUIAgent, build the graph
with create_base_agent(copilotkit=True), derive the graphId from the default
agent, and log it for the v2 frontend route to match.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage** (against `2026-06-24-copilotkit-v2-alignment-design.md`, sub-project 1):
- "add CopilotKitMiddleware behind a flag" → Task 2. ✓
- "swap to copilotkit LangGraphAGUIAgent, keep CORS + Langfuse, path /agent" → Task 3. ✓
- "derive graphId from get_default_agent() or 'dynagent', log it" → Task 3 (Step 3 + Step 6). ✓
- "add copilotkit to [copilotkit-ui] extra" → Task 1. ✓
- "StateStreamingMiddleware deferred to step 5" → honored (Global Constraints). ✓
- Acceptance: default stack unchanged → Task 2 default tests; copilotkit=True appends one → Task 2; server mounts + logs id → Task 3; extra installs → Task 1; tests/lint/type pass → per-task Steps. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/vague steps; every code step shows full code. ✓

**Type consistency:** `build_middleware_stack(model, *, sync_mode=False, copilotkit=False) -> list[AgentMiddleware[Any, Any]]` defined in Task 2 and consumed by `create_base_agent`'s `copilotkit` flag (Task 2) and `create_copilotkit_app` (Task 3, via `copilotkit=True`). `get_default_agent() -> str | None` matches the `or "dynagent"` fallback. Patch targets (`copilotkit_server.get_default_agent`, `copilotkit_server.create_base_agent`, `copilotkit.LangGraphAGUIAgent`, `ag_ui_langgraph.add_langgraph_fastapi_endpoint`) match the import sites in the Task 3 code. ✓
