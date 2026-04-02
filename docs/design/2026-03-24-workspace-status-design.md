# Workspace Status & Pipeline Progress

**Date**: 2026-03-25
**Domain**: Nurture + Designer
**Status**: Draft (Rev 4 — batch two-level tracking, batch_invoker callbacks, Designer prompt changes)

## Problem

IDP developers have no way to check workspace status — which files have been generated/modified and where the pipeline is at — without manually inspecting the git clone. This blocks visibility into both the Nurture code-generation pipeline and Designer LLD section completion.

## User Story

> As an IDP Developer, I want to see the status of files generated/modified and pipeline progress in my workspace, so I can track what's done and what's still running without leaving Chainlit.

## Requirements

- Works in both Nurture and Designer Chainlit servers
- Uses existing session context (user_name, repo_name, jira_number) — no manual input
- Near real-time pipeline progress with item-level granularity (e.g., "PartyBehaviour: in progress")
- Two-level Nurture progress: batch-level status + per-item status within each batch
- Programmatic creation of all progress entries before batch processing begins
- Git-style file diff summary for the workspace
- Single-file unified diff on conversational request
- Open to any GitHub-authenticated user (no per-user access control)
- Progress data stored in Postgres for post-facto analysis

## Architecture

Progress tracking operates at two levels, both writing to the same `workspace_progress` table via the shared `update_progress()` function:

```
┌─────────────────────────────────────────────────────────────┐
│  AGENT LEVEL (Designer + conversational flows)               │
│                                                              │
│  TodoListMiddleware (LangChain built-in, opt-in)             │
│    → injects write_todos tool; agents plan & track steps     │
│    → enabled via create_base_agent(enable_todos=True)        │
│                                                              │
│  ProgressPersistenceMiddleware (new, shared-lib, opt-in)     │
│    → after_model hook reads todos from state                 │
│    → calls update_progress() to persist to Postgres          │
│    → resolves workspace via context store (set_context_key   │
│      _resolver pattern)                                      │
│    → enabled via create_base_agent(progress_domain="...")     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    update_progress()
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  workspace_progress (Postgres)                               │
│  - Queryable by user_name, repo_name, jira_number            │
│  - Upsert by (jira_number, repo_name, stage, item)           │
└──────────────────────────▲──────────────────────────────────┘
                           │
                    update_progress()
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  ORCHESTRATOR LEVEL (Nurture pipeline)                       │
│                                                              │
│  model_orch / behaviour_orch / scenario_orch                 │
│    → pre-populate all items as "pending" before batch start  │
│    → create batch-level "__batch__" entry as "in_progress"   │
│    → batch_invoker callbacks update per-item status           │
│    → update batch-level entry on completion/failure           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (Chainlit)                               │
│                                                              │
│  /Workspace-Status slash command                             │
│    → queries workspace_progress → pipeline progress view     │
│    → calls /gitStatus on file server → git diff view         │
│                                                              │
│  mer_git_diff_tool (conversational)                          │
│    → single-file unified diff on request                     │
└─────────────────────────────────────────────────────────────┘
```

**Key principles**:
- `update_progress()` is a plain function (following the `fn` → `fn_tool` pattern). Two callers: middleware (agent-level) and orchestrators (pipeline-level).
- Agents use `write_todos` naturally via `TodoListMiddleware`. They don't know about persistence.
- Workspace identity resolved via context store using `set_context_key_resolver()` pattern — middleware stays in shared-lib, use-case agnostic.
- All LangChain middleware dependencies are hidden behind `create_base_agent()` parameters. Callers never import LangChain middleware directly.
- Nurture progress is pre-populated (all items as "pending") before batch starts, then updated via `batch_invoker` callbacks.

## Components

### 1. create_base_agent() — Opt-in Middleware Parameters

**Location**: `autobots-devtools-shared-lib`, `base_agent.py`

Two new parameters on `create_base_agent()`. All LangChain middleware is encapsulated — callers see only Dynagent's API:

```python
def create_base_agent(
    checkpointer=None,
    sync_mode=False,
    initial_agent_name=None,
    state_schema=Dynagent,
    enable_todos=False,           # NEW — adds TodoListMiddleware
    progress_domain=None,         # NEW — adds ProgressPersistenceMiddleware
):
    middleware = [_middleware]

    if enable_todos:
        middleware.append(TodoListMiddleware())

    if progress_domain:
        middleware.append(ProgressPersistenceMiddleware(domain=progress_domain))

    middleware.append(SummarizationMiddleware(...))

    return create_agent(model, ..., middleware=middleware)
```

**Domain usage** — no LangChain imports in any domain code:

```python
# Designer server.py — todos ON, progress ON
agent = create_base_agent(enable_todos=True, progress_domain="designer")

# Nurture server.py — todos OFF (orchestrator handles progress), progress ON for any conversational agents
agent = create_base_agent(enable_todos=False, progress_domain="nurture")
```

**No state schema change required.** `TodoListMiddleware` defines its own `PlanningState` with a `todos` field. `create_agent` auto-merges middleware state schemas into the resolved state. The `todos` field is present only when `enable_todos=True`, without modifying `Dynagent`.

### 2. update_progress() Function

**Location**: `autobots-devtools-shared-lib`, new module (e.g., `common/utils/progress_utils.py`)

A plain function — no tool decorator. Follows the existing `fn` → `fn_tool` pattern. Both the middleware and orchestrators call this.

```python
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
    """
    # INSERT ... ON CONFLICT (jira_number, repo_name, stage, item)
    # DO UPDATE SET status = ..., user_name = ..., thread_id = ..., updated_at = now()
```

No-op if Postgres is not configured (no `MER_DATABASE_URL`).

### 3. ProgressPersistenceMiddleware

**Location**: `autobots-devtools-shared-lib` (internal — not exposed to callers)

A thin `after_model` hook that mirrors agent-level todos to the `workspace_progress` table. Resolves workspace identity via the context store using the existing `set_context_key_resolver()` pattern — no dependency on `MerState`.

```python
from langgraph.config import get_config

class ProgressPersistenceMiddleware(AgentMiddleware):
    def __init__(self, domain: str):
        super().__init__()
        self.domain = domain

    def after_model(self, state, runtime):
        todos = state.get("todos", [])
        if not todos:
            return None

        context_key = resolve_context_key(state)
        context = get_context(context_key)
        config = get_config()
        thread_id = config["configurable"].get("thread_id")

        for todo in todos:
            update_progress(
                user_name=context.get("user_name", ""),
                repo_name=context.get("repo_name", ""),
                jira_number=context.get("jira_number", ""),
                domain=self.domain,
                stage=state.get("agent_name", "unknown"),
                item=todo["content"],
                status=todo["status"],
                thread_id=thread_id,
            )
        return None
```

**Note**: `Runtime` does not expose `config` directly. Use `get_config()` from `langgraph.config` to access the thread_id. This is the standard LangGraph pattern for accessing config within middleware.

### 4. batch_invoker() — Generic Callbacks

**Location**: `autobots-devtools-shared-lib`, `dynagent/agents/batch.py`

Add generic callback parameters to `batch_invoker`. The shared-lib defines the contract; callers supply the implementation:

```python
def batch_invoker(
    agent_name: str,
    records: list[str],
    callbacks: list[Any] | None = None,
    enable_tracing: bool = True,
    trace_metadata: TraceMetadata | None = None,
    on_item_start: Callable[[int, str], None] | None = None,      # NEW
    on_item_complete: Callable[[int, str, bool], None] | None = None,  # NEW
) -> BatchResult:
    """Run prompts in parallel.

    Args:
        on_item_start: Called before each item is processed.
            Receives (index, record).
        on_item_complete: Called after each item completes.
            Receives (index, record, success).
    """
    # ... for each record:
    if on_item_start:
        on_item_start(index, record)
    result = invoke_agent(...)
    if on_item_complete:
        on_item_complete(index, record, result.success)
```

The shared-lib is generic — no knowledge of `update_progress` or MER concepts. Callers supply lambdas.

### 5. Orchestrator Instrumentation (Nurture) — Two-Level Progress

**Location**: `autobots-agents-mer/domains/nurture/services/` — `model_orch.py`, `behaviour_orch.py`, `scenario_orch.py`

Each orchestrator creates **N+1 entries** for a batch of N items: one `__batch__` sentinel for the overall batch, plus one per item. All items are pre-populated as `pending` before processing begins.

```python
# Example: model_orch.py with 10 models → 11 entries
def run_model_batch(models, user_name, repo_name, jira_number):
    stage = "model-oas-generator"

    # 1. Create batch-level entry
    update_progress(user_name, repo_name, jira_number, "nurture",
                    stage, "__batch__", "in_progress")

    # 2. Pre-populate all items as pending
    for model in models:
        update_progress(user_name, repo_name, jira_number, "nurture",
                        stage, model["name"], "pending")

    # 3. Build prompts list (existing logic)
    prompts = [serialize_model_prompt(m) for m in models]

    # 4. Run batch with callbacks — each item updates its own status
    result = batch_invoker(
        "model-oas-generator", prompts,
        on_item_start=lambda i, r: update_progress(
            user_name, repo_name, jira_number, "nurture",
            stage, models[i]["name"], "in_progress"),
        on_item_complete=lambda i, r, ok: update_progress(
            user_name, repo_name, jira_number, "nurture",
            stage, models[i]["name"], "completed" if ok else "failed"),
    )

    # 5. Update batch-level status
    batch_status = "completed" if result.failures == 0 else "failed"
    update_progress(user_name, repo_name, jira_number, "nurture",
                    stage, "__batch__", batch_status)
```

**Example: Model Batch with 10 models → 11 rows in workspace_progress:**

| stage | item | status |
|---|---|---|
| `model-oas-generator` | `__batch__` | `in_progress` |
| `model-oas-generator` | `Party` | `completed` |
| `model-oas-generator` | `Account` | `completed` |
| `model-oas-generator` | `Address` | `in_progress` |
| `model-oas-generator` | `CustomerProfile` | `pending` |
| ... | ... | ... |

The slash command renders both levels:

```
Model OAS Generation: 🔄 In Progress (3/10 complete)
  ✅ Party
  ✅ Account
  🔄 Address
  ⬚  CustomerProfile
  ⬚  Transaction
  ...
```

### 6. Postgres Table — `workspace_progress`

```sql
CREATE TABLE workspace_progress (
    id            SERIAL PRIMARY KEY,
    thread_id     TEXT,
    user_name     TEXT NOT NULL,
    repo_name     TEXT NOT NULL,
    jira_number   TEXT NOT NULL,
    domain        TEXT NOT NULL,        -- "nurture" | "designer"
    stage         TEXT NOT NULL,        -- "model-oas-generator" | "background" etc.
    item          TEXT NOT NULL,        -- "PartyBehaviour" | "__batch__" | "Background Section"
    status        TEXT NOT NULL,        -- "pending" | "in_progress" | "completed" | "failed"
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(jira_number, repo_name, stage, item)
);

CREATE INDEX idx_wp_user   ON workspace_progress(user_name);
CREATE INDEX idx_wp_repo   ON workspace_progress(repo_name);
CREATE INDEX idx_wp_jira   ON workspace_progress(jira_number);
```

**Status values**: `pending`, `in_progress`, `completed`, `failed`. The `failed` status allows orchestrators to explicitly record failures in their exception handlers, distinguishing failed items from slow-running ones.

**Upsert key**: `(jira_number, repo_name, stage, item)`. Re-running the pipeline in a new session overwrites stale progress. `thread_id` is stored for traceability but is not part of the upsert key.

**Sentinel item**: `__batch__` is a reserved item name used for batch-level status. The slash command reads `__batch__` rows to show overall batch status and counts items (excluding `__batch__`) for the "3/10 complete" summary.

### 7. File Server Git Endpoints

**Location**: `autobots-devtools-shared-lib`, file server (`app.py`)

Two new endpoints on the existing file server (runs on the same machine as the git clone):

#### `POST /gitStatus`

Runs `git status --porcelain` + `git diff --stat` on the workspace.

```python
class GitStatusBody(BaseModel):
    workspace_context: dict[str, Any] = {}
    session_id: str | None = None
```

Returns staged files, unstaged modifications, and untracked files with line-change counts.

#### `POST /gitDiff`

Runs `git diff -- <file_path>` for a single file. Returns unified diff.

```python
class GitDiffBody(BaseModel):
    workspace_context: dict[str, Any] = {}
    file_path: str              # relative path within workspace
    session_id: str | None = None
```

**Security**: All git commands use `subprocess.run()` with list form (no `shell=True`) and the `--` separator to prevent argument injection. Workspace path validated via existing `_path_under_root()`.

### 8. MER Tools

**Location**: `autobots-agents-mer/common/tools/`

| Tool | Calls | Purpose |
|---|---|---|
| `mer_git_status_tool` | `POST /gitStatus` | Returns formatted git status for workspace |
| `mer_git_diff_tool` | `POST /gitDiff` | Returns unified diff for a single file |

Both tools resolve workspace context from `runtime.state` (user_name, repo_name, jira_number).

### 9. `/Workspace-Status` Slash Command

**Location**: `autobots-agents-mer/common/` — registered by both Nurture and Designer servers.

**Takes no arguments** — pulls user_name, repo_name, jira_number from session context.

**Renders two sections in a single Chainlit message:**

#### Pipeline Progress (from `workspace_progress` table)

Queries by `(user_name, repo_name, jira_number)`. Groups by stage, reads `__batch__` for batch-level status and counts items for summary:

```
NURTURE PIPELINE
================
Model Extraction: ✅ Completed
  ✅ Party
  ✅ Account
  ✅ Address

Model OAS Generation: 🔄 In Progress (2/3 complete)
  ✅ Party.json
  ✅ Account.json
  🔄 Address.json

Behaviour Generation: 🔄 In Progress (1/4 complete)
  ✅ PartySearchBehaviour — done
  🔄 PartyCreateBehaviour — in progress
  ❌ AccountSearchBehaviour — failed
  ⬚  AccountCreateBehaviour — yet to start

Scenario Generation: ⬚ Not Started
  ⬚  (not started)
```

For Designer, progress maps to the known section agents:

```
DESIGNER SECTIONS
=================
  ✅ Background
  ✅ Data Models
  🔄 Logical Processing Units
  ⬚  Services
  ⬚  Test Data
  ⬚  Validation
  ⬚  LLD Consolidation
```

#### File Changes (from `/gitStatus`)

```
FILE CHANGES (git)
==================
Staged:
  A  generated/Party.json                    (+142)
  A  generated/Account.json                  (+98)

Modified (unstaged):
  M  docs/FeatureLLD/MER-74405/background.md (+12, -3)

Untracked:
  ?  agentic-generator-meta/fbp-model-meta/MER-74405/model_list.json
  ?  generated/PartySearchBehaviour.java
```

#### Single-File Diff (conversational follow-up)

After seeing the status, developer can ask "show me the diff for generated/Party.json" — the agent calls `mer_git_diff_tool` and renders the unified diff in chat.

### 10. Designer Prompt Changes

**Location**: `autobots-agents-mer/agent_configs/designer/prompts/`

**Applies to**: Multi-step Designer agents (`background.md`, `data_models.md`, `logical_processing_units.md`, and future agents: `service.md`, `test_data.md`, `validation.md`, `lld_consolidator.md`). Does **not** apply to `coordinator.md` (it just routes).

**Does not apply to**: Nurture batch agents — their progress is tracked by orchestrator callbacks, not by agent-level todos.

Following the [Golden Prompt Template](../golden-prompt.md) and [Golden Prompt Guidelines](../Golden_Prompt_Guidelines.md), add `write_todos` as a tool reference in `<tools>` and a step 0 in `<workflow>`:

#### `<tools>` section — add `write_todos` sub-tag

```xml
<tools>
  <!-- existing tools... -->

  <tool name="write_todos">
    <usage>
    Use to declare your planned steps at the start of work and update status
    as you complete each step.
    WHY: Progress is tracked and visible to the developer via /Workspace-Status.
    Statuses: "pending" (not started), "in_progress" (working on it), "completed" (done).
    </usage>
  </tool>
</tools>
```

#### `<workflow>` section — add step 0

```xml
<workflow>
  <step n="0">
    Declare your plan using write_todos

    Call `write_todos` with a list of the steps you will take, each with
    status "pending".
    WHY: This populates the progress tracker so the developer can monitor
    your work via /Workspace-Status.
  </step>

  <step n="1" parallel="true" depends_on="0">
    Initialize context and discover files
    ...
  </step>

  <!-- existing steps renumbered from here -->
</workflow>
```

#### `<validation>` section — add todo completion check

```xml
<validation>
  ...
  N. All todos created in step 0 have been updated to "completed" via write_todos.
</validation>
```

**Example**: For the `background.md` agent, step 0 would create todos like:

```
write_todos([
    {"content": "Read existing background document", "status": "pending"},
    {"content": "Ask user about business context", "status": "pending"},
    {"content": "Draft background section", "status": "pending"},
    {"content": "Confirm with user", "status": "pending"},
    {"content": "Save background to workspace", "status": "pending"},
])
```

As the agent completes each step, it calls `write_todos` again with updated statuses. The `ProgressPersistenceMiddleware` mirrors each update to `workspace_progress`.

## Data Flow

```
NURTURE PIPELINE EXECUTION:
  Orchestrator pre-populates progress
    → creates __batch__ entry as "in_progress"
    → creates all item entries as "pending"
  batch_invoker runs with callbacks
    → on_item_start: update_progress(item, "in_progress")
    → on_item_complete: update_progress(item, "completed" | "failed")
  Orchestrator finalizes
    → updates __batch__ entry to "completed" | "failed"

DESIGNER CONVERSATION:
  Agent starts work
    → calls write_todos with all planned steps as "pending" (step 0)
    → ProgressPersistenceMiddleware mirrors to workspace_progress
  Agent works through steps
    → calls write_todos with updated statuses after each step
    → ProgressPersistenceMiddleware mirrors each update

DEVELOPER CHECKS STATUS:
  Types /Workspace-Status in Chainlit
    → reads session context (user_name, repo_name, jira_number)
    → queries workspace_progress → pipeline progress view
      → __batch__ rows for batch-level status + item counts
      → item rows for per-item detail
    → calls /gitStatus on file server → git diff view
    → renders both in single Chainlit message

  Asks "show diff for Party.json"
    → agent calls mer_git_diff_tool
    → tool calls /gitDiff on file server
    → renders unified diff in chat
```

## Edge Cases

- **Context not set**: Slash command returns "Please set workspace context first (use View-Context)."
- **Postgres unavailable**: `update_progress()` is a no-op; pipeline execution is not blocked. Slash command shows "Progress tracking unavailable" with git status still working.
- **Dirty git state**: `/gitStatus` reports whatever `git status` reports — merge conflicts, detached HEAD, etc. are shown as-is.
- **Re-run pipeline**: Upsert key `(jira_number, repo_name, stage, item)` means re-runs overwrite previous status. No duplicate rows.
- **Batch item failure**: `on_item_complete` callback writes `"failed"` status. Batch-level `__batch__` entry set to `"failed"` if any item fails.
- **Partial batch failure**: Some items `completed`, some `failed`. `__batch__` shows `failed`. Slash command shows per-item breakdown so developer sees exactly what failed.

## Query Examples

```sql
-- All progress for a Jira ticket
SELECT stage, item, status, updated_at
FROM workspace_progress
WHERE jira_number = 'MER-74405'
ORDER BY stage, CASE WHEN item = '__batch__' THEN 0 ELSE 1 END, updated_at;

-- Batch-level summary only (one row per stage)
SELECT stage, status, updated_at
FROM workspace_progress
WHERE jira_number = 'MER-74405'
  AND item = '__batch__';

-- Per-item detail for a specific stage
SELECT item, status, updated_at
FROM workspace_progress
WHERE jira_number = 'MER-74405'
  AND stage = 'model-oas-generator'
  AND item != '__batch__'
ORDER BY updated_at;

-- All my active workspaces
SELECT DISTINCT repo_name, jira_number, domain
FROM workspace_progress
WHERE user_name = 'pralhad'
  AND status NOT IN ('completed', 'failed');

-- Failed items across all workspaces
SELECT user_name, repo_name, jira_number, stage, item, updated_at
FROM workspace_progress
WHERE status = 'failed'
  AND item != '__batch__';

-- Stuck items (in_progress for over an hour)
SELECT user_name, repo_name, jira_number, stage, item, updated_at
FROM workspace_progress
WHERE status = 'in_progress'
  AND updated_at < now() - interval '1 hour';
```

## Security

- `/Workspace-Status` requires GitHub OAuth (existing Chainlit auth)
- File server git endpoints use same workspace_context validation as existing endpoints (path traversal protection via `_path_under_root`)
- Git commands use `subprocess.run()` with list form (no `shell=True`) and `--` separator to prevent argument injection
- Git commands are read-only (`git status`, `git diff`) — no write operations

## Dependencies

- All LangChain middleware dependencies encapsulated within `create_base_agent()` — no direct imports by consumers
- Existing: Postgres (MER_DATABASE_URL), file server, Chainlit
- No new infrastructure required
