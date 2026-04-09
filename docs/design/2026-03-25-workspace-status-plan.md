# Workspace Status & Pipeline Progress — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give IDP developers real-time pipeline progress and git-diff visibility inside Chainlit, with Postgres-backed analytics.

**Architecture:** Two-level progress tracking — orchestrator-level for Nurture batch pipelines, agent-level via TodoListMiddleware for Designer conversations — both writing to a shared `workspace_progress` table via `update_progress()`. File-change visibility via new git endpoints on the existing file server.

**Tech Stack:** Python 3.12+, SQLModel, FastAPI, LangChain agents middleware, Chainlit, Postgres, subprocess (git)

**Spec:** `docs/design/2026-03-24-workspace-status-design.md`

**Note:** The spec places `update_progress()` in shared-lib (`common/utils/progress_utils.py`). This plan places it in MER (`common/services/progress_service.py`) because it depends on MER's DB engine. The shared-lib middleware uses a callback pattern (`set_progress_callback`) to stay decoupled. DB tables are created via `SQLModel.metadata.create_all()` (existing pattern) — no Alembic migrations needed for dev; production migration can be added later if needed.

---

### Task 1: Postgres Model — `WorkspaceProgressEntity`

Create the SQLModel ORM entity for the `workspace_progress` table. Follows the exact pattern of `MerContextEntity` in `autobots-agents-mer/src/autobots_agents_mer/common/db/models.py`.

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/common/db/models_progress.py`
- Modify: `autobots-agents-mer/src/autobots_agents_mer/common/db/engine.py:10` (add import so `create_all` picks up new table)
- Test: `autobots-agents-mer/tests/unit/common/test_models_progress.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/common/test_models_progress.py
"""Unit tests for WorkspaceProgressEntity model."""
import pytest
from autobots_agents_mer.common.db.models_progress import WorkspaceProgressEntity


class TestWorkspaceProgressEntity:
    def test_table_name(self):
        assert WorkspaceProgressEntity.__tablename__ == "workspace_progress"

    def test_required_fields(self):
        """All non-nullable fields must be present in model_fields."""
        required = {"user_name", "repo_name", "jira_number", "domain", "stage", "item", "status"}
        field_names = set(WorkspaceProgressEntity.model_fields.keys())
        assert required.issubset(field_names)

    def test_optional_thread_id(self):
        """thread_id is optional (nullable)."""
        entity = WorkspaceProgressEntity(
            user_name="u", repo_name="r", jira_number="J-1",
            domain="nurture", stage="model-oas-generator", item="Party", status="pending",
        )
        assert entity.thread_id is None

    def test_unique_constraint_columns(self):
        """Verify the unique constraint covers (jira_number, repo_name, stage, item)."""
        from sqlmodel import SQLModel
        table = SQLModel.metadata.tables["workspace_progress"]
        unique_constraints = [
            c for c in table.constraints
            if hasattr(c, "columns") and len(c.columns) == 4
        ]
        assert len(unique_constraints) == 1
        col_names = {col.name for col in unique_constraints[0].columns}
        assert col_names == {"jira_number", "repo_name", "stage", "item"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_models_progress.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autobots_agents_mer.common.db.models_progress'`

- [ ] **Step 3: Write the implementation**

```python
# autobots-agents-mer/src/autobots_agents_mer/common/db/models_progress.py
# ABOUTME: SQLModel entity for the workspace_progress table.
# ABOUTME: Tracks pipeline progress per (jira_number, repo_name, stage, item).

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class WorkspaceProgressEntity(SQLModel, table=True):
    """Persistent ORM table for pipeline/agent progress tracking."""

    __tablename__ = "workspace_progress"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("jira_number", "repo_name", "stage", "item", name="uq_wp_jira_repo_stage_item"),
    )

    id: int | None = Field(default=None, primary_key=True)
    thread_id: str | None = Field(default=None, description="LangGraph thread_id for traceability")
    user_name: str = Field(description="Logged-in user identifier")
    repo_name: str = Field(description="Repository name")
    jira_number: str = Field(description="Jira ticket number", index=True)
    domain: str = Field(description="nurture | designer")
    stage: str = Field(description="Agent/pipeline stage name")
    item: str = Field(description="Entity name or __batch__ sentinel")
    status: str = Field(description="pending | in_progress | completed | failed")
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )
```

- [ ] **Step 4: Import in engine.py so create_all picks up the table**

In `autobots-agents-mer/src/autobots_agents_mer/common/db/engine.py`, add after line 10:

```python
from autobots_agents_mer.common.db.models_progress import WorkspaceProgressEntity  # noqa: F401
```

- [ ] **Step 5: Create `__init__.py` if missing and run tests**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_models_progress.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Commit**

```bash
cd autobots-agents-mer
git add src/autobots_agents_mer/common/db/models_progress.py src/autobots_agents_mer/common/db/engine.py tests/unit/common/test_models_progress.py
git commit -m "feat: add WorkspaceProgressEntity model for pipeline progress tracking"
```

---

### Task 2: `update_progress()` Function

The core upsert function. Lives in MER (not shared-lib) because it uses MER's DB engine. Plain function — no `@tool` decorator. No-op when Postgres is unavailable.

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/common/services/progress_service.py`
- Test: `autobots-agents-mer/tests/unit/common/test_progress_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/common/test_progress_service.py
"""Unit tests for update_progress and get_progress."""
from unittest.mock import MagicMock, patch

import pytest


class TestUpdateProgress:
    @patch("autobots_agents_mer.common.services.progress_service.get_session_factory")
    def test_upsert_creates_new_record(self, mock_get_sf):
        from autobots_agents_mer.common.services.progress_service import update_progress

        mock_session = MagicMock()
        mock_sf = MagicMock(return_value=mock_session)
        mock_get_sf.return_value = mock_sf
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        # Should not raise
        update_progress(
            user_name="alice", repo_name="repo", jira_number="MER-1",
            domain="nurture", stage="model-oas-generator", item="Party", status="pending",
        )
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("autobots_agents_mer.common.services.progress_service.get_session_factory", side_effect=RuntimeError("not init"))
    def test_noop_when_db_unavailable(self, mock_get_sf):
        from autobots_agents_mer.common.services.progress_service import update_progress

        # Should not raise — graceful no-op
        update_progress(
            user_name="alice", repo_name="repo", jira_number="MER-1",
            domain="nurture", stage="model-oas-generator", item="Party", status="pending",
        )


class TestGetProgress:
    @patch("autobots_agents_mer.common.services.progress_service.get_session_factory")
    def test_returns_list_of_dicts(self, mock_get_sf):
        from autobots_agents_mer.common.services.progress_service import get_progress

        mock_session = MagicMock()
        mock_sf = MagicMock(return_value=mock_session)
        mock_get_sf.return_value = mock_sf
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.all.return_value = []

        result = get_progress(user_name="alice", repo_name="repo", jira_number="MER-1")
        assert isinstance(result, list)

    @patch("autobots_agents_mer.common.services.progress_service.get_session_factory", side_effect=RuntimeError("not init"))
    def test_returns_empty_when_db_unavailable(self, mock_get_sf):
        from autobots_agents_mer.common.services.progress_service import get_progress

        result = get_progress(user_name="alice", repo_name="repo", jira_number="MER-1")
        assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_progress_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# autobots-agents-mer/src/autobots_agents_mer/common/services/progress_service.py
# ABOUTME: Progress tracking service — update_progress (upsert) and get_progress (query).
# ABOUTME: No-op when Postgres is not initialised; never blocks pipeline execution.

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


def update_progress(
    user_name: str,
    repo_name: str,
    jira_number: str,
    domain: str,
    stage: str,
    item: str,
    status: str,
    thread_id: str | None = None,
) -> None:
    """Upsert a single progress record to workspace_progress.

    Status values: "pending", "in_progress", "completed", "failed".
    No-op if Postgres is not configured (get_session_factory raises RuntimeError).
    """
    try:
        from autobots_agents_mer.common.db.engine import get_session_factory

        session_factory = get_session_factory()
    except RuntimeError:
        logger.debug("DB not initialised — progress update skipped")
        return

    stmt = text("""
        INSERT INTO workspace_progress (user_name, repo_name, jira_number, domain, stage, item, status, thread_id, updated_at)
        VALUES (:user_name, :repo_name, :jira_number, :domain, :stage, :item, :status, :thread_id, now())
        ON CONFLICT (jira_number, repo_name, stage, item)
        DO UPDATE SET status = :status, user_name = :user_name, thread_id = :thread_id, updated_at = now()
    """)

    with session_factory() as session:
        session.execute(stmt, {
            "user_name": user_name,
            "repo_name": repo_name,
            "jira_number": jira_number,
            "domain": domain,
            "stage": stage,
            "item": item,
            "status": status,
            "thread_id": thread_id,
        })
        session.commit()


def get_progress(
    user_name: str,
    repo_name: str,
    jira_number: str,
) -> list[dict[str, Any]]:
    """Query all progress records for a workspace.

    Returns list of dicts with keys: stage, item, status, updated_at, domain.
    Returns empty list if Postgres is not configured.
    """
    try:
        from autobots_agents_mer.common.db.engine import get_session_factory

        session_factory = get_session_factory()
    except RuntimeError:
        logger.debug("DB not initialised — progress query skipped")
        return []

    stmt = text("""
        SELECT stage, item, status, domain, updated_at
        FROM workspace_progress
        WHERE user_name = :user_name AND repo_name = :repo_name AND jira_number = :jira_number
        ORDER BY stage, CASE WHEN item = '__batch__' THEN 0 ELSE 1 END, updated_at
    """)

    with session_factory() as session:
        rows = session.execute(stmt, {
            "user_name": user_name,
            "repo_name": repo_name,
            "jira_number": jira_number,
        }).all()
        return [
            {"stage": r.stage, "item": r.item, "status": r.status, "domain": r.domain, "updated_at": r.updated_at}
            for r in rows
        ]
```

- [ ] **Step 4: Run tests**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_progress_service.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
cd autobots-agents-mer
git add src/autobots_agents_mer/common/services/progress_service.py tests/unit/common/test_progress_service.py
git commit -m "feat: add update_progress and get_progress for workspace progress tracking"
```

---

### Task 3: `batch_invoker` Callback Parameters

Add `on_item_start` and `on_item_complete` generic callback parameters to `batch_invoker()` in shared-lib. The shared-lib is generic — no knowledge of progress concepts.

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/batch.py:180-325`
- Test: `autobots-devtools-shared-lib/tests/unit/test_batch.py` (add new test class)

- [ ] **Step 1: Write the failing test**

Add to `autobots-devtools-shared-lib/tests/unit/test_batch.py`:

```python
# ---------------------------------------------------------------------------
# batch_invoker callback signature validation
# ---------------------------------------------------------------------------


class TestBatchInvokerCallbackSignature:
    """Verify batch_invoker accepts on_item_start and on_item_complete params."""

    def test_accepts_callback_params(self):
        """batch_invoker should accept on_item_start and on_item_complete keyword args.
        We test the function signature; actual execution requires a real agent."""
        import inspect

        sig = inspect.signature(batch_invoker)
        param_names = list(sig.parameters.keys())
        assert "on_item_start" in param_names
        assert "on_item_complete" in param_names

    def test_callback_params_default_to_none(self):
        import inspect

        sig = inspect.signature(batch_invoker)
        assert sig.parameters["on_item_start"].default is None
        assert sig.parameters["on_item_complete"].default is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_batch.py::TestBatchInvokerCallbackSignature -v`
Expected: FAIL — `on_item_start` not in param_names

- [ ] **Step 3: Add callback parameters to batch_invoker signature**

In `batch.py`, update the `batch_invoker` function signature (line ~180) to add the two new params. Also add the `Callable` import:

```python
# Add to imports at top of file:
from collections.abc import Callable

# Updated signature:
def batch_invoker(
    agent_name: str,
    records: list[str],
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
    checkpointer: Any = None,
    input_state: dict[str, Any] | None = None,
    config: RunnableConfig | None = None,
    state_schema: type[AgentState[ResponseT]] = Dynagent,
    on_item_start: Callable[[int, str], None] | None = None,
    on_item_complete: Callable[[int, str, bool], None] | None = None,
) -> BatchResult:
```

Update the docstring to document the new params:

```
    Args:
        ...existing args...
        on_item_start: Called before each item is processed.
            Receives (index, record). Called sequentially before batch dispatch.
        on_item_complete: Called after each item completes.
            Receives (index, record, success).
```

- [ ] **Step 4: Implement callback invocations**

**Important:** `agent.batch()` dispatches all items in parallel internally, so we cannot fire `on_item_start` per-item as they begin. Instead:
- `on_item_start` fires pre-batch for ALL items (all go to "in_progress" simultaneously). This is acceptable because the orchestrator pre-populates items as "pending", and the batch is the transition to "in_progress".
- `on_item_complete` fires per-item as results are collected (this IS per-item, after `.batch()` returns).

In the batch execution section (around lines 292-310), add callback calls around `agent.batch()`:

```python
                # --- Fire on_item_start callbacks (pre-batch, all items) ---
                if on_item_start:
                    for idx, record in enumerate(records):
                        try:
                            on_item_start(idx, record)
                        except Exception:
                            logger.warning("on_item_start callback failed for index %d", idx, exc_info=True)

                # --- Execute in parallel (thread pool via .batch) ---
                raw_outputs: list[Any] = agent.batch(
                    inputs,
                    config=configs,
                    return_exceptions=True,
                )

                # --- Wrap raw outputs into BatchResult + fire on_item_complete ---
                results: list[RecordResult] = []
                for idx, output in enumerate(raw_outputs):
                    if isinstance(output, BaseException):
                        results.append(RecordResult(index=idx, success=False, error=str(output)))
                        if on_item_complete:
                            try:
                                on_item_complete(idx, records[idx], False)
                            except Exception:
                                logger.warning("on_item_complete callback failed for index %d", idx, exc_info=True)
                    else:
                        content = _extract_last_ai_content(output)
                        results.append(RecordResult(index=idx, success=True, output=content))
                        if on_item_complete:
                            try:
                                on_item_complete(idx, records[idx], True)
                            except Exception:
                                logger.warning("on_item_complete callback failed for index %d", idx, exc_info=True)
```

- [ ] **Step 5: Run all batch tests**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_batch.py -v`
Expected: PASS (all existing tests + 2 new)

- [ ] **Step 6: Commit**

```bash
cd autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/agents/batch.py tests/unit/test_batch.py
git commit -m "feat: add on_item_start/on_item_complete callbacks to batch_invoker"
```

---

### Task 4: `create_base_agent()` — Opt-in Middleware Parameters

Add `enable_todos` and `progress_domain` params to `create_base_agent()`. All LangChain middleware is encapsulated — callers never import middleware directly.

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/base_agent.py`
- Test: `autobots-devtools-shared-lib/tests/unit/test_base_agent_params.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_base_agent_params.py
"""Unit tests for create_base_agent opt-in parameters."""
import inspect

from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent


class TestCreateBaseAgentSignature:
    def test_accepts_enable_todos(self):
        sig = inspect.signature(create_base_agent)
        assert "enable_todos" in sig.parameters
        assert sig.parameters["enable_todos"].default is False

    def test_accepts_progress_domain(self):
        sig = inspect.signature(create_base_agent)
        assert "progress_domain" in sig.parameters
        assert sig.parameters["progress_domain"].default is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_base_agent_params.py -v`
Expected: FAIL — `enable_todos` not in sig.parameters

- [ ] **Step 3: Add parameters and middleware wiring**

Update `base_agent.py`:

```python
def create_base_agent(
    checkpointer: Any = None,
    sync_mode: bool = False,
    initial_agent_name: str | None = None,
    state_schema: type[AgentState[ResponseT]] = Dynagent,
    enable_todos: bool = False,
    progress_domain: str | None = None,
) -> CompiledStateGraph:
    """Create the dynagent base agent with middleware.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
            Defaults to InMemorySaver.
        sync_mode: Whether to use synchronous middleware (for batch processing).
        initial_agent_name: Override the default agent from agents.yaml.
        state_schema: State schema class. Defaults to Dynagent.
        enable_todos: When True, adds TodoListMiddleware (injects write_todos tool).
        progress_domain: When set (e.g. "designer"), adds ProgressPersistenceMiddleware
            that mirrors agent todos to workspace_progress table.
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Warm the singleton
    AgentMeta.instance()

    model = lm()

    # All registry tools — middleware controls which subset is active per agent
    all_tools = get_all_tools()

    _middleware = inject_agent_sync if sync_mode else inject_agent_async

    middleware_stack: list[Any] = [_middleware]

    if enable_todos:
        from langchain.agents.middleware import TodoListMiddleware

        middleware_stack.append(TodoListMiddleware())

    if progress_domain:
        from autobots_devtools_shared_lib.dynagent.agents.progress_middleware import (
            ProgressPersistenceMiddleware,
        )

        middleware_stack.append(ProgressPersistenceMiddleware(domain=progress_domain))

    middleware_stack.append(
        SummarizationMiddleware(
            model=model,
            trigger=("fraction", 0.6),
            keep=("messages", 20),
        ),
    )

    if initial_agent_name is None:
        initial_agent_name = get_default_agent()

    return create_agent(
        model,
        name=initial_agent_name or "dynagent",
        tools=all_tools,
        state_schema=state_schema,
        middleware=cast(
            "list[AgentMiddleware[Any, Any]]",
            middleware_stack,
        ),
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4: Create stub progress_middleware module**

This is needed so the import doesn't fail. Full implementation in Task 5.

```python
# autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/progress_middleware.py
# ABOUTME: ProgressPersistenceMiddleware — mirrors agent todos to workspace_progress table.
# ABOUTME: Stub; full implementation follows in a later task.

from langchain.agents.middleware import AgentMiddleware


class ProgressPersistenceMiddleware(AgentMiddleware):
    """Persist agent-level todos to workspace_progress (Postgres)."""

    def __init__(self, domain: str):
        super().__init__()
        self.domain = domain
```

- [ ] **Step 5: Run tests**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_base_agent_params.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/agents/base_agent.py src/autobots_devtools_shared_lib/dynagent/agents/progress_middleware.py tests/unit/test_base_agent_params.py
git commit -m "feat: add enable_todos and progress_domain opt-in params to create_base_agent"
```

---

### Task 5: `ProgressPersistenceMiddleware` — Full Implementation

Implement the `after_model` hook that reads todos from state and calls `update_progress()`. Uses `set_context_key_resolver()` pattern for workspace identity resolution.

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/progress_middleware.py`
- Test: `autobots-devtools-shared-lib/tests/unit/test_progress_middleware.py`

**Note:** This middleware calls `update_progress()` from MER. To keep shared-lib decoupled, it uses a **progress callback** pattern: the middleware accepts a callable at init time. `create_base_agent` doesn't wire this — the domain server does. _However_, to keep the API simple per the spec (just `progress_domain`), we'll use a module-level registry similar to `set_context_key_resolver`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_progress_middleware.py
"""Unit tests for ProgressPersistenceMiddleware."""
from unittest.mock import MagicMock, patch

from autobots_devtools_shared_lib.dynagent.agents.progress_middleware import (
    ProgressPersistenceMiddleware,
    set_progress_callback,
)


class TestProgressPersistenceMiddleware:
    def test_domain_stored(self):
        mw = ProgressPersistenceMiddleware(domain="designer")
        assert mw.domain == "designer"

    def test_after_model_noop_when_no_todos(self):
        """Should return None when state has no todos."""
        mw = ProgressPersistenceMiddleware(domain="nurture")
        result = mw.after_model({"agent_name": "bg"}, MagicMock())
        assert result is None

    @patch("autobots_devtools_shared_lib.dynagent.agents.progress_middleware._progress_callback")
    @patch("autobots_devtools_shared_lib.common.utils.context_utils.get_context")
    @patch("autobots_devtools_shared_lib.common.utils.context_utils.resolve_context_key")
    def test_after_model_calls_callback_for_each_todo(self, mock_resolve, mock_get_ctx, mock_cb):
        mock_resolve.return_value = "alice"
        mock_get_ctx.return_value = {
            "user_name": "alice", "repo_name": "repo", "jira_number": "MER-1",
        }

        mw = ProgressPersistenceMiddleware(domain="designer")
        state = {
            "agent_name": "background",
            "todos": [
                {"content": "Read docs", "status": "completed"},
                {"content": "Draft section", "status": "in_progress"},
            ],
        }
        mw.after_model(state, MagicMock())
        assert mock_cb.call_count == 2


class TestSetProgressCallback:
    def test_set_and_clear(self):
        cb = MagicMock()
        set_progress_callback(cb)
        # Cleanup
        set_progress_callback(None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_progress_middleware.py -v`
Expected: FAIL — `cannot import name 'set_progress_callback'`

- [ ] **Step 3: Implement the full middleware**

```python
# autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/progress_middleware.py
# ABOUTME: ProgressPersistenceMiddleware — mirrors agent todos to workspace_progress.
# ABOUTME: Uses a module-level callback so shared-lib stays decoupled from MER's DB.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.context_utils import (
    get_context,
    resolve_context_key,
)

logger = get_logger(__name__)

# Module-level callback: (user_name, repo_name, jira_number, domain, stage, item, status, thread_id) -> None
_progress_callback: Callable[..., None] | None = None


def set_progress_callback(
    callback: Callable[..., None] | None,
) -> None:
    """Register the progress persistence callback.

    Called once at domain startup (e.g. in nurture/designer server.py) to wire
    update_progress() from MER into the shared-lib middleware.
    Pass None to clear.
    """
    global _progress_callback
    _progress_callback = callback


class ProgressPersistenceMiddleware(AgentMiddleware):
    """Persist agent-level todos to workspace_progress (Postgres).

    Runs as an after_model hook: reads todos from state, resolves workspace
    identity via context store, and calls the registered progress callback.
    """

    def __init__(self, domain: str):
        super().__init__()
        self.domain = domain

    def after_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        todos = state.get("todos")
        if not todos:
            return None

        if _progress_callback is None:
            logger.debug("No progress callback registered — skipping persistence")
            return None

        try:
            context_key = resolve_context_key(state)
            context = get_context(context_key)

            # Resolve thread_id from LangGraph config
            thread_id: str | None = None
            try:
                from langgraph.config import get_config

                config = get_config()
                thread_id = config.get("configurable", {}).get("thread_id")
            except Exception:
                logger.debug("Could not resolve thread_id from config", exc_info=True)

            agent_name = state.get("agent_name", "unknown")

            for todo in todos:
                _progress_callback(
                    user_name=context.get("user_name", ""),
                    repo_name=context.get("repo_name", ""),
                    jira_number=context.get("jira_number", ""),
                    domain=self.domain,
                    stage=agent_name,
                    item=todo.get("content", "unknown"),
                    status=todo.get("status", "pending"),
                    thread_id=thread_id,
                )
        except Exception:
            logger.warning("ProgressPersistenceMiddleware failed", exc_info=True)

        return None
```

- [ ] **Step 4: Run tests**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_progress_middleware.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/dynagent/agents/progress_middleware.py tests/unit/test_progress_middleware.py
git commit -m "feat: implement ProgressPersistenceMiddleware with callback pattern"
```

---

### Task 6: File Server Git Endpoints

Add `POST /gitStatus` and `POST /gitDiff` endpoints to the existing file server. Both use `subprocess.run()` with list form and `--` separator for security.

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/common/servers/fileserver/models.py` (add request models)
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/common/servers/fileserver/app.py` (add endpoints)
- Test: `autobots-devtools-shared-lib/tests/unit/test_fileserver_git.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_fileserver_git.py
"""Unit tests for file server git endpoints."""
from unittest.mock import patch, MagicMock
import subprocess

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with a temp root dir."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["FILE_SERVER_ROOT"] = tmpdir
        # Re-import to pick up new root
        from autobots_devtools_shared_lib.common.servers.fileserver.app import app
        yield TestClient(app)


class TestGitStatusEndpoint:
    @patch("autobots_devtools_shared_lib.common.servers.fileserver.app.subprocess")
    def test_returns_status_and_diff_stat(self, mock_subprocess, client):
        mock_subprocess.run.side_effect = [
            MagicMock(returncode=0, stdout=" M file.py\n?? new.txt\n", stderr=""),
            MagicMock(returncode=0, stdout=" 1 file changed, 10 insertions(+)\n", stderr=""),
        ]
        resp = client.post("/gitStatus", json={"workspace_context": {}, "session_id": "s1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "porcelain" in data
        assert "diff_stat" in data


class TestGitDiffEndpoint:
    @patch("autobots_devtools_shared_lib.common.servers.fileserver.app.subprocess")
    def test_returns_unified_diff(self, mock_subprocess, client):
        mock_subprocess.run.return_value = MagicMock(
            returncode=0, stdout="diff --git a/file.py b/file.py\n+added line\n", stderr=""
        )
        resp = client.post("/gitDiff", json={
            "workspace_context": {},
            "file_path": "file.py",
            "session_id": "s1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "diff" in data

    def test_rejects_empty_file_path(self, client):
        resp = client.post("/gitDiff", json={
            "workspace_context": {},
            "file_path": "",
        })
        assert resp.status_code == 422  # validation error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_fileserver_git.py -v`
Expected: FAIL — 404 (endpoints don't exist)

- [ ] **Step 3: Add request models**

Append to `models.py`:

```python
class GitStatusBody(BaseModel):
    workspace_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Workspace scoping context (needs workspace_base_path).",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for trace correlation/logging.",
    )


class GitDiffBody(BaseModel):
    workspace_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Workspace scoping context (needs workspace_base_path).",
    )
    file_path: str = Field(description="Relative path within workspace for diff.")
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for trace correlation/logging.",
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("file_path cannot be empty")
        return _validate_no_path_traversal(v)
```

- [ ] **Step 4: Add endpoints to app.py**

Add `import subprocess` at the top of `app.py`, then add the new model imports and endpoints:

```python
# Add to imports from models:
from autobots_devtools_shared_lib.common.servers.fileserver.models import (
    GitDiffBody,
    GitStatusBody,
    ListFilesBody,
    MoveFileBody,
    ReadFileBody,
    WriteFileBody,
)

# Add after createDownloadLink endpoint:

@app.post("/gitStatus")
def git_status(body: GitStatusBody) -> dict[str, Any]:
    """Run git status --porcelain and git diff --stat on the workspace."""
    set_session_id(body.session_id or "default_session_id")
    workspace_root = _path_under_root(body.workspace_context, None)
    logger.info("gitStatus called workspace_root=%s", workspace_root)

    if not workspace_root.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    porcelain_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    diff_stat_result = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        timeout=30,
    )

    logger.info("gitStatus success workspace_root=%s", workspace_root)
    return {
        "porcelain": porcelain_result.stdout,
        "diff_stat": diff_stat_result.stdout,
        "errors": porcelain_result.stderr + diff_stat_result.stderr,
    }


@app.post("/gitDiff")
def git_diff(body: GitDiffBody) -> dict[str, Any]:
    """Run git diff for a single file. Returns unified diff."""
    set_session_id(body.session_id or "default_session_id")
    workspace_root = _path_under_root(body.workspace_context, None)
    logger.info("gitDiff called file_path=%s workspace_root=%s", body.file_path, workspace_root)

    if not workspace_root.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Use list form + -- separator to prevent argument injection
    result = subprocess.run(
        ["git", "diff", "--", body.file_path],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        timeout=30,
    )

    logger.info("gitDiff success file_path=%s", body.file_path)
    return {
        "diff": result.stdout,
        "errors": result.stderr,
    }
```

- [ ] **Step 5: Run tests**

Run: `cd autobots-devtools-shared-lib && make test-one TEST=tests/unit/test_fileserver_git.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd autobots-devtools-shared-lib
git add src/autobots_devtools_shared_lib/common/servers/fileserver/models.py src/autobots_devtools_shared_lib/common/servers/fileserver/app.py tests/unit/test_fileserver_git.py
git commit -m "feat: add /gitStatus and /gitDiff endpoints to file server"
```

---

### Task 7: MER Git Tools — `mer_git_status_tool` and `mer_git_diff_tool`

New `@tool` functions that proxy to the file server git endpoints. Follow the existing pattern in `workspace_tools.py`.

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/common/tools/git_tools.py`
- Test: `autobots-agents-mer/tests/unit/common/test_git_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/common/test_git_tools.py
"""Unit tests for MER git tools."""
from unittest.mock import MagicMock, patch

import pytest


class TestMerGitStatusTool:
    @patch("autobots_agents_mer.common.tools.git_tools.mer_git_status")
    def test_returns_formatted_status(self, mock_fn):
        from autobots_agents_mer.common.tools.git_tools import mer_git_status_tool

        mock_fn.return_value = " M file.py\n?? new.txt"
        runtime = MagicMock()
        runtime.state = {"user_name": "alice", "repo_name": "r", "jira_number": "J-1"}

        result = mer_git_status_tool.func(runtime)
        mock_fn.assert_called_once_with(state=runtime.state)
        assert result == " M file.py\n?? new.txt"


class TestMerGitDiffTool:
    @patch("autobots_agents_mer.common.tools.git_tools.mer_git_diff")
    def test_returns_diff(self, mock_fn):
        from autobots_agents_mer.common.tools.git_tools import mer_git_diff_tool

        mock_fn.return_value = "diff --git a/f.py b/f.py\n+new line"
        runtime = MagicMock()
        runtime.state = {"user_name": "alice"}

        result = mer_git_diff_tool.func(runtime, file_path="f.py")
        mock_fn.assert_called_once_with("f.py", state=runtime.state)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_git_tools.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# autobots-agents-mer/src/autobots_agents_mer/common/tools/git_tools.py
# ABOUTME: MER git tools — mer_git_status_tool and mer_git_diff_tool.
# ABOUTME: Proxy to file server /gitStatus and /gitDiff endpoints.

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
from langchain.tools import ToolRuntime, tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
# Use the same URL constant as all other file server calls in shared-lib
from autobots_devtools_shared_lib.common.utils.fserver_client_utils import FILE_SERVER_BASE_URL

from autobots_agents_mer.common.models.state import MerState
# Use the same workspace context resolution as existing MER tools
from autobots_agents_mer.common.utils.context_utils import get_workspace_context

logger = get_logger(__name__)


def mer_git_status(state: Mapping[str, Any] | None = None) -> str:
    """Call /gitStatus on the file server and return formatted output."""
    wc = get_workspace_context(state)
    url = f"{FILE_SERVER_BASE_URL}/gitStatus"
    payload: dict[str, Any] = {"workspace_context": wc}
    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    parts = []
    if data.get("porcelain"):
        parts.append(data["porcelain"])
    if data.get("diff_stat"):
        parts.append(data["diff_stat"])
    return "\n".join(parts) if parts else "No changes detected."


def mer_git_diff(file_path: str, state: Mapping[str, Any] | None = None) -> str:
    """Call /gitDiff on the file server for a single file."""
    wc = get_workspace_context(state)
    url = f"{FILE_SERVER_BASE_URL}/gitDiff"
    payload: dict[str, Any] = {"workspace_context": wc, "file_path": file_path}
    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("diff", "") or "No diff available."


@tool
def mer_git_status_tool(
    runtime: ToolRuntime[None, MerState],
) -> str:
    """Show git status (changed, staged, and untracked files) for the workspace."""
    return mer_git_status(state=runtime.state)


@tool
def mer_git_diff_tool(
    runtime: ToolRuntime[None, MerState],
    file_path: str = "",
) -> str:
    """Show the unified diff for a single file in the workspace."""
    return mer_git_diff(file_path, state=runtime.state)
```

- [ ] **Step 4: Run tests**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_git_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd autobots-agents-mer
git add src/autobots_agents_mer/common/tools/git_tools.py tests/unit/common/test_git_tools.py
git commit -m "feat: add mer_git_status_tool and mer_git_diff_tool"
```

---

### Task 8: Orchestrator Instrumentation — Nurture Two-Level Progress

Add `update_progress()` calls to the Nurture orchestrators for two-level (batch + per-item) progress tracking. Instrument `model_orch.py` first as the pattern, then `behaviour_orch.py` and `scenario_orch.py`.

**Files:**
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/nurture/services/model_orch.py`
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/nurture/services/behaviour_orch.py`
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/nurture/services/scenario_orch.py`
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/nurture/utils/agent_utils.py` (add callbacks to `run_nurture_batch`)
- Test: `autobots-agents-mer/tests/unit/nurture/test_model_orch_progress.py`

- [ ] **Step 1: Write the failing test for model_orch progress tracking**

```python
# tests/unit/nurture/test_model_orch_progress.py
"""Test that model_orch instruments progress via update_progress."""
from unittest.mock import MagicMock, call, patch

import pytest


class TestModelOrchProgress:
    @patch("autobots_agents_mer.domains.nurture.services.model_orch.update_progress")
    @patch("autobots_agents_mer.domains.nurture.services.model_orch._step_oas_generator")
    @patch("autobots_agents_mer.domains.nurture.services.model_orch._step_model_list_generator")
    def test_pre_populates_and_finalises_batch(self, mock_list_gen, mock_oas_gen, mock_progress):
        from autobots_agents_mer.domains.nurture.services.model_orch import trigger_model_orch

        mock_list_gen.return_value = {"model_list": [{"name": "Party"}, {"name": "Account"}]}

        state = {
            "messages": [],
            "user_name": "alice",
            "repo_name": "repo",
            "jira_number": "MER-1",
        }

        trigger_model_orch(state)

        # Should have pre-populated: __batch__ as in_progress, Party as pending, Account as pending
        calls = mock_progress.call_args_list
        assert any(
            c.kwargs.get("item") == "__batch__" and c.kwargs.get("status") == "in_progress"
            for c in calls
        ), f"Expected __batch__ in_progress call, got: {calls}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/nurture/test_model_orch_progress.py -v`
Expected: FAIL — `update_progress` not found in model_orch

- [ ] **Step 3: Add progress instrumentation to `run_nurture_batch` in agent_utils.py**

Add callback support to `run_nurture_batch()`:

```python
# In agent_utils.py, add import at top:
from autobots_agents_mer.common.services.progress_service import update_progress

# Update run_nurture_batch to accept and pass callbacks:
def run_nurture_batch(
    parse_fn: Callable,
    agent_name: str,
    item_list: dict | list,
    user_id: str,
    repo_name: str,
    jira_number: str,
    state: MerState | None = None,
    on_item_start: Callable[[int, str], None] | None = None,
    on_item_complete: Callable[[int, str, bool], None] | None = None,
) -> BatchResult:
    # ... existing code ...
    return nurture_batch(
        agent_name=agent_name,
        records=records,
        user_id=user_id,
        repo_name=repo_name,
        jira_number=jira_number,
        session_id=session_id,
        on_item_start=on_item_start,
        on_item_complete=on_item_complete,
    )
```

And update `nurture_batch()` in `nurture_batch.py` to forward callbacks to `batch_invoker`:

1. Add `Callable` import at top:
```python
from collections.abc import Callable
```

2. Add params to `nurture_batch` signature (after `session_id`):
```python
    on_item_start: Callable[[int, str], None] | None = None,
    on_item_complete: Callable[[int, str, bool], None] | None = None,
```

3. Pass callbacks to `batch_invoker` call (around line 106):
```python
    result = batch_invoker(
        agent_name,
        records,
        trace_metadata=trace_metadata,
        input_state={"user_name": user_id} if user_id else None,
        config={"recursion_limit": 50},
        on_item_start=on_item_start,
        on_item_complete=on_item_complete,
    )
```

- [ ] **Step 4: Instrument model_orch.py**

In `model_orch.py`, add progress tracking to `trigger_model_orch`:

```python
# Add import:
from autobots_agents_mer.common.services.progress_service import update_progress

# Modify trigger_model_orch — after getting model_list and before _step_oas_generator:
def trigger_model_orch(state: MerState, *, supervised: bool = False) -> None:
    if supervised:
        from autobots_agents_mer.domains.nurture.tools.nurture_tools import register_nurture_tools
        register_nurture_tools()

    try:
        model_list = _step_model_list_generator(state)
        models = model_list.get("model_list", [])
        user_name = state.get(USER_NAME, "")
        repo_name = state.get(REPO_NAME, "")
        jira_number = state.get(JIRA_NUMBER, "")
        stage = MODEL_MD_GENERATOR

        # Pre-populate progress: batch + all items as pending
        update_progress(user_name=user_name, repo_name=repo_name, jira_number=jira_number,
                        domain="nurture", stage=stage, item="__batch__", status="in_progress")
        for m in models:
            name = m["name"] if isinstance(m, dict) else str(m)
            update_progress(user_name=user_name, repo_name=repo_name, jira_number=jira_number,
                            domain="nurture", stage=stage, item=name, status="pending")

        # Run OAS batch with per-item callbacks
        _step_oas_generator_with_progress(state, model_list, models)

        # Finalise batch
        update_progress(user_name=user_name, repo_name=repo_name, jira_number=jira_number,
                        domain="nurture", stage=stage, item="__batch__", status="completed")
        logger.info("Model orchestration complete.")
    except Exception:
        # Mark batch as failed
        try:
            update_progress(user_name=state.get(USER_NAME, ""), repo_name=state.get(REPO_NAME, ""),
                            jira_number=state.get(JIRA_NUMBER, ""),
                            domain="nurture", stage=MODEL_MD_GENERATOR, item="__batch__", status="failed")
        except Exception:
            logger.warning("Failed to mark batch as failed", exc_info=True)
        if supervised:
            logger.exception("Error during generation")
        else:
            raise
```

Modify the existing `_trigger_model_list_generator_batch` to accept optional callbacks, then use it in `_step_oas_generator`:

```python
# Update existing function signature to accept callbacks:
def _trigger_model_list_generator_batch(
    model_list: dict | list,
    state: MerState,
    on_item_start: Callable[[int, str], None] | None = None,
    on_item_complete: Callable[[int, str, bool], None] | None = None,
) -> BatchResult:
    user_id: str = state.get(USER_NAME, "")
    repo_name: str = state.get(REPO_NAME, "")
    jira_number: str = state.get(JIRA_NUMBER, "")
    return run_nurture_batch(
        parse_model_list, MODEL_MD_GENERATOR, model_list,
        user_id, repo_name, jira_number, state,
        on_item_start=on_item_start,
        on_item_complete=on_item_complete,
    )
```

Add a progress-aware helper that wraps `_step_oas_generator`:

```python
def _step_oas_generator_with_progress(state: MerState, model_list: dict, models: list) -> None:
    """Step 2 with per-item progress callbacks."""
    user_name = state.get(USER_NAME, "")
    repo_name = state.get(REPO_NAME, "")
    jira_number = state.get(JIRA_NUMBER, "")
    stage = MODEL_MD_GENERATOR

    def _name(i: int) -> str:
        m = models[i]
        return m["name"] if isinstance(m, dict) else str(m)

    with otel_span("nurture-step-model-oas"):
        batch = _trigger_model_list_generator_batch(
            model_list, state,
            on_item_start=lambda i, r: update_progress(
                user_name=user_name, repo_name=repo_name, jira_number=jira_number,
                domain="nurture", stage=stage, item=_name(i), status="in_progress"),
            on_item_complete=lambda i, r, ok: update_progress(
                user_name=user_name, repo_name=repo_name, jira_number=jira_number,
                domain="nurture", stage=stage, item=_name(i),
                status="completed" if ok else "failed"),
        )
        _validate_batch_success(batch, MODEL_MD_GENERATOR)
        log_batches(batch, "OAS batch")
```

Also add `Callable` to the imports in model_orch.py:

```python
from collections.abc import Callable
```

Apply the same pattern to `behaviour_orch.py` and `scenario_orch.py` — each has an equivalent `_trigger_*_batch` function that gets the same callback parameters and a `_step_*_with_progress` wrapper.

- [ ] **Step 5: Run tests**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/nurture/test_model_orch_progress.py -v`
Expected: PASS

- [ ] **Step 6: Lint and type-check**

Run: `cd autobots-agents-mer && make lint && make type-check`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
cd autobots-agents-mer
git add -A src/autobots_agents_mer/domains/nurture/services/ src/autobots_agents_mer/domains/nurture/utils/agent_utils.py src/autobots_agents_mer/domains/nurture/services/nurture_batch.py tests/unit/nurture/
git commit -m "feat: add two-level progress tracking to nurture orchestrators"
```

---

### Task 9: `/Workspace-Status` Slash Command

Register a `/Workspace-Status` command in both Nurture and Designer servers. The command queries progress from Postgres and git status from the file server, then renders a combined Chainlit message.

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/common/services/workspace_status.py`
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/nurture/server.py` (register command + handler)
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/designer/command_handlers.py` (register command + handler)
- Test: `autobots-agents-mer/tests/unit/common/test_workspace_status.py`

- [ ] **Step 1: Write the failing test for the formatter**

```python
# tests/unit/common/test_workspace_status.py
"""Unit tests for workspace status formatting."""
from autobots_agents_mer.common.services.workspace_status import format_progress


class TestFormatProgress:
    def test_empty_progress(self):
        result = format_progress([])
        assert "No progress data" in result

    def test_batch_and_items(self):
        rows = [
            {"stage": "model-oas-generator", "item": "__batch__", "status": "in_progress", "domain": "nurture", "updated_at": None},
            {"stage": "model-oas-generator", "item": "Party", "status": "completed", "domain": "nurture", "updated_at": None},
            {"stage": "model-oas-generator", "item": "Account", "status": "in_progress", "domain": "nurture", "updated_at": None},
            {"stage": "model-oas-generator", "item": "Address", "status": "pending", "domain": "nurture", "updated_at": None},
        ]
        result = format_progress(rows)
        assert "Party" in result
        assert "Account" in result
        assert "Address" in result

    def test_failed_items_shown(self):
        rows = [
            {"stage": "behaviour-java", "item": "__batch__", "status": "failed", "domain": "nurture", "updated_at": None},
            {"stage": "behaviour-java", "item": "PartySearch", "status": "failed", "domain": "nurture", "updated_at": None},
        ]
        result = format_progress(rows)
        assert "failed" in result.lower() or "Failed" in result


class TestFormatGitStatus:
    def test_empty_output(self):
        from autobots_agents_mer.common.services.workspace_status import format_git_status
        result = format_git_status("", "")
        assert "No file changes" in result

    def test_modified_and_untracked(self):
        from autobots_agents_mer.common.services.workspace_status import format_git_status
        porcelain = " M src/file.py\n?? new.txt\n"
        result = format_git_status(porcelain, "")
        assert "file.py" in result
        assert "new.txt" in result

    def test_staged_files(self):
        from autobots_agents_mer.common.services.workspace_status import format_git_status
        porcelain = "A  staged.py\n"
        result = format_git_status(porcelain, "")
        assert "staged.py" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_workspace_status.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement workspace_status.py**

```python
# autobots-agents-mer/src/autobots_agents_mer/common/services/workspace_status.py
# ABOUTME: Workspace status rendering — combines pipeline progress + git status.
# ABOUTME: Used by /Workspace-Status slash command in both Nurture and Designer.

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)

_STATUS_ICON = {
    "completed": "✅",
    "in_progress": "🔄",
    "pending": "⬚",
    "failed": "❌",
}


def format_progress(rows: list[dict[str, Any]]) -> str:
    """Format progress rows into a human-readable string.

    Groups by stage, shows batch-level summary + per-item breakdown.
    """
    if not rows:
        return "No progress data available."

    # Group by stage, preserving order
    stages: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        stage = row["stage"]
        if stage not in stages:
            stages[stage] = []
        stages[stage].append(row)

    lines: list[str] = []
    for stage, items in stages.items():
        batch_row = next((r for r in items if r["item"] == "__batch__"), None)
        real_items = [r for r in items if r["item"] != "__batch__"]

        # Stage header
        completed_count = sum(1 for r in real_items if r["status"] == "completed")
        total_count = len(real_items)

        if batch_row:
            icon = _STATUS_ICON.get(batch_row["status"], "?")
            status_label = batch_row["status"].replace("_", " ").title()
            if real_items:
                lines.append(f"{_format_stage_name(stage)}: {icon} {status_label} ({completed_count}/{total_count} complete)")
            else:
                lines.append(f"{_format_stage_name(stage)}: {icon} {status_label}")
        elif real_items:
            lines.append(f"{_format_stage_name(stage)}:")

        for r in real_items:
            icon = _STATUS_ICON.get(r["status"], "?")
            lines.append(f"  {icon} {r['item']}")

    return "\n".join(lines)


def _format_stage_name(stage: str) -> str:
    """Convert agent-name style to human-readable: model-oas-generator → Model OAS Generation."""
    return stage.replace("-", " ").replace("_", " ").title()


def format_git_status(porcelain: str, diff_stat: str) -> str:
    """Format git status output for display."""
    if not porcelain.strip() and not diff_stat.strip():
        return "No file changes detected."

    lines: list[str] = ["FILE CHANGES (git)", "=" * 18]

    staged = []
    modified = []
    untracked = []

    for line in porcelain.strip().split("\n"):
        if not line.strip():
            continue
        xy = line[:2]
        path = line[3:]
        if xy[0] == "?" and xy[1] == "?":
            untracked.append(f"  ?  {path}")
        elif xy[0] != " ":
            staged.append(f"  {xy[0]}  {path}")
        elif xy[1] != " ":
            modified.append(f"  {xy[1]}  {path}")

    if staged:
        lines.append("\nStaged:")
        lines.extend(staged)
    if modified:
        lines.append("\nModified (unstaged):")
        lines.extend(modified)
    if untracked:
        lines.append("\nUntracked:")
        lines.extend(untracked)

    if diff_stat.strip():
        lines.append(f"\n{diff_stat.strip()}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `cd autobots-agents-mer && make test-one TEST=tests/unit/common/test_workspace_status.py -v`
Expected: PASS

- [ ] **Step 5: Wire into Nurture server.py**

Add the `Workspace-Status` command to the commands list in `nurture/server.py`:

```python
# Add to commands list:
{"id": "Workspace-Status", "icon": "activity", "description": "View workspace status and pipeline progress"},
```

Add handler in `_get_preloaded_prompt`:

```python
if msg.command == "Workspace-Status":
    return "__WORKSPACE_STATUS__"  # sentinel handled in on_message
```

In `on_message`, before agent invocation, add:

```python
if message.content == "__WORKSPACE_STATUS__" or message.command == "Workspace-Status":
    from autobots_agents_mer.common.services.workspace_status import format_progress, format_git_status
    from autobots_agents_mer.common.services.progress_service import get_progress
    from autobots_agents_mer.common.tools.git_tools import mer_git_status

    user_id = cl.user_session.get("user_id") or ""
    from autobots_devtools_shared_lib.common.utils.context_utils import get_context
    ctx = get_context(user_id)
    repo_name = ctx.get("repo_name", "")
    jira_number = ctx.get("jira_number", "")

    if not repo_name or not jira_number:
        await cl.Message(content="Please set workspace context first (use Edit-Context).").send()
        return

    progress = get_progress(user_name=user_id, repo_name=repo_name, jira_number=jira_number)
    progress_text = format_progress(progress)

    try:
        git_raw = mer_git_status(state={"user_name": user_id, "repo_name": repo_name, "jira_number": jira_number})
        git_text = git_raw
    except Exception:
        git_text = "Git status unavailable."

    await cl.Message(content=f"**PIPELINE PROGRESS**\n```\n{progress_text}\n```\n\n**{git_text}**").send()
    return
```

- [ ] **Step 6: Wire into Designer command_handlers.py**

Add command and handler following the existing pattern. The `Workspace-Status` command is a deterministic handler (no agent involvement):

```python
# Add to COMMANDS list:
{
    "id": "Workspace-Status",
    "icon": "activity",
    "description": "View workspace status and pipeline progress",
},

# Add deterministic handler:
async def handle_workspace_status() -> None:
    """Show workspace progress and git status."""
    from autobots_agents_mer.common.services.workspace_status import format_progress, format_git_status
    from autobots_agents_mer.common.services.progress_service import get_progress
    from autobots_agents_mer.common.tools.git_tools import mer_git_status

    ctx = _get_user_context()
    user_name = ctx.get(CTX_USER_NAME, "")
    repo_name = ctx.get(CTX_REPO_NAME, "")
    jira_number = ctx.get(CTX_JIRA_NUMBER, "")

    if not repo_name or not jira_number:
        await cl.Message(content="Please set workspace context first.").send()
        return

    progress = get_progress(user_name=user_name, repo_name=repo_name, jira_number=jira_number)
    progress_text = format_progress(progress)

    try:
        git_raw = mer_git_status(state={"user_name": user_name, "repo_name": repo_name, "jira_number": jira_number})
    except Exception:
        git_raw = "Git status unavailable."

    await cl.Message(content=f"**PIPELINE PROGRESS**\n```\n{progress_text}\n```\n\n**{git_raw}**").send()

# Register:
_DETERMINISTIC_HANDLERS["Workspace-Status"] = handle_workspace_status
```

- [ ] **Step 7: Commit**

```bash
cd autobots-agents-mer
git add src/autobots_agents_mer/common/services/workspace_status.py src/autobots_agents_mer/domains/nurture/server.py src/autobots_agents_mer/domains/designer/command_handlers.py tests/unit/common/test_workspace_status.py
git commit -m "feat: add /Workspace-Status slash command for both Nurture and Designer"
```

---

### Task 10: Wire Progress Callback in Domain Servers

Register the `update_progress` function from MER as the progress callback in shared-lib's `ProgressPersistenceMiddleware`. This is the glue that connects the shared-lib middleware to MER's database.

**Files:**
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/designer/server.py` (add callback + enable_todos + progress_domain)
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/nurture/server.py` (add callback + progress_domain)

- [ ] **Step 1: Wire designer server.py**

```python
# In designer/server.py, after register_designer_tools() and before @cl.on_chat_start:

# Wire progress callback so ProgressPersistenceMiddleware can persist to Postgres
from autobots_devtools_shared_lib.dynagent.agents.progress_middleware import set_progress_callback
from autobots_agents_mer.common.services.progress_service import update_progress
set_progress_callback(update_progress)

# In @cl.on_chat_start, update create_base_agent call:
base_agent = create_base_agent(enable_todos=True, progress_domain="designer")
```

- [ ] **Step 2: Wire nurture server.py**

```python
# In nurture/server.py, after register_nurture_tools():

# Wire progress callback for any conversational agents
from autobots_devtools_shared_lib.dynagent.agents.progress_middleware import set_progress_callback
from autobots_agents_mer.common.services.progress_service import update_progress
set_progress_callback(update_progress)

# In @cl.on_chat_start, optionally add progress_domain:
base_agent = create_base_agent(progress_domain="nurture")
```

- [ ] **Step 3: Register git tools in both domains**

In nurture's `register_nurture_tools()`, add:
```python
from autobots_agents_mer.common.tools.git_tools import mer_git_status_tool, mer_git_diff_tool
# Add to the tools list passed to register_usecase_tools
```

In designer's `register_designer_tools()`, add the same.

**Note on `agents.yaml`**: The git tools are for the coordinator agent (slash command and conversational use). Add `mer_git_status_tool` and `mer_git_diff_tool` to the coordinator's `tools:` list in both `agent_configs/nurture/agents.yaml` and `agent_configs/designer/agents.yaml`.

- [ ] **Step 4: Verify servers start without errors**

Run (manual check):
```bash
cd autobots-agents-mer
DYNAGENT_CONFIG_ROOT_DIR=agent_configs/designer python -c "from autobots_agents_mer.domains.designer import server; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
cd autobots-agents-mer
git add src/autobots_agents_mer/domains/designer/server.py src/autobots_agents_mer/domains/nurture/server.py
git commit -m "feat: wire progress callback and opt-in middleware in domain servers"
```

---

### Task 11: Designer Prompt Changes — Aligned to Golden Prompt

Update the 3 active Designer agent prompts (`background.md`, `data_models.md`, `logical_processing_units.md`) to include `write_todos` tool reference, step 0, and validation check. Follows the Golden Prompt Template.

**Files:**
- Modify: `autobots-agents-mer/agent_configs/designer/prompts/background.md`
- Modify: `autobots-agents-mer/agent_configs/designer/prompts/data_models.md`
- Modify: `autobots-agents-mer/agent_configs/designer/prompts/logical_processing_units.md`

**Note:** `coordinator.md` is NOT modified (it just routes). Prompts for agents not yet wired (`service.md`, `test_data.md`, `validation.md`, `lld_consolidator.md`) are NOT modified.

- [ ] **Step 1: Update background.md**

Add `write_todos` to the Tools section:

```markdown
## Tools

get_agent_list - extracts list of agents available for handoff

### write_todos
Use to declare your planned steps at the start of work and update status as you complete each step.
WHY: Progress is tracked and visible to the developer via /Workspace-Status.
Statuses: "pending" (not started), "in_progress" (working on it), "completed" (done).
```

Add Step 0 before the Pre Processing Steps:

```markdown
### Step 0: Declare Plan

Before starting, call `write_todos` with your planned steps, each with status "pending":
- Read context and workspace files
- Ask user about business context
- Draft background section
- Confirm with user
- Save background to workspace

WHY: This populates the progress tracker so the developer can monitor your work via /Workspace-Status.
```

Add validation at end of Completion section:

```markdown
**Validation:** All todos created in Step 0 must be updated to "completed" via write_todos before handing off.
```

- [ ] **Step 2: Update data_models.md**

Apply the same pattern: add `write_todos` tool, add Step 0 declaring model-specific steps, add validation check.

- [ ] **Step 3: Update logical_processing_units.md**

Apply the same pattern.

- [ ] **Step 4: Commit**

```bash
cd autobots-agents-mer
git add agent_configs/designer/prompts/background.md agent_configs/designer/prompts/data_models.md agent_configs/designer/prompts/logical_processing_units.md
git commit -m "feat: add write_todos to Designer prompts for progress tracking"
```

---

### Task 12: Quality Gates — Lint, Type-Check, All Tests

Run full quality checks across both repos.

**Files:** None (verification only)

- [ ] **Step 1: Run shared-lib checks**

```bash
cd autobots-devtools-shared-lib && make all-checks
```
Expected: PASS

- [ ] **Step 2: Run MER checks**

```bash
cd autobots-agents-mer && make all-checks
```
Expected: PASS

- [ ] **Step 3: Fix any issues and re-run**

If any check fails, fix and re-run until all pass.

- [ ] **Step 4: Final commit if needed**

```bash
# Only if fixes were needed
git commit -m "fix: resolve lint/type-check/test issues from workspace status feature"
```
