# React CopilotKit / AG-UI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream a Dynagent LangGraph agent into a React chat UI (CopilotKit on the AG-UI protocol) with streaming-chat parity to the current Chainlit experience, without touching the existing graph, tools, config, or tracing.

**Architecture:** A new generic FastAPI app factory in shared-lib (`create_copilotkit_app`) wraps the existing `create_base_agent()` graph in an AG-UI agent and mounts it on a FastAPI route — parallel to how `default_ui.py` is a drop-in Chainlit entry point. A new Next.js reference app under `ui/` proxies browser requests to that FastAPI endpoint via a `CopilotRuntime` route handler (keeping any provider keys server-side) and renders CopilotKit's prebuilt `<CopilotChat>`.

**Tech Stack:** Python 3.12+, FastAPI, `ag-ui-langgraph` (CopilotKit Python SDK); Next.js (App Router) with `@copilotkit/runtime`, `@copilotkit/react-core`, `@copilotkit/react-ui`.

## Global Constraints

- **Python:** `>=3.12,<4.0.0`. Formatter/linter Ruff, line-length 100, double quotes. Every new `.py` file starts with a two-line `# ABOUTME:` header (matching `default_ui.py`/`ui_utils.py`).
- **Optional dependency:** `ag-ui-langgraph` is an **optional** Python dependency group (`copilotkit-ui`), not a core dependency — invoke/batch-only consumers must not pull it. Verified current version: `ag-ui-langgraph>=0.0.42` (released 2026-06-19; Python `>=3.10,<3.15`).
- **AG-UI Python API (verified 0.0.42):** `from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint`. Constructor: `LangGraphAgent(name=..., description=..., graph=...)`. Registration: `add_langgraph_fastapi_endpoint(app, agent, path)`.
- **Agent identity (must match across all three layers):** AG-UI agent `name` = `"coordinator"`; FastAPI mount path = `"/agent"`; Next.js `agents` key = `coordinator`; React `agent` prop = `"coordinator"`.
- **Next.js runtime API (verified, June 2026 CopilotKit docs):** `CopilotRuntime`, `ExperimentalEmptyAdapter`, `copilotRuntimeNextJSAppRouterEndpoint` from `@copilotkit/runtime`; `LangGraphHttpAgent` from `@copilotkit/runtime/langgraph` (constructor takes `{ url }`). `ExperimentalEmptyAdapter` is correct because the Dynagent graph does its own LLM calls.
- **Reuse, don't modify:** `create_base_agent()`, the LangGraph graph, tools, config loading, and Langfuse/OTel tracing are used as-is. No edits to `base_agent.py`, `invocation_utils.py`, `ui_utils.py`, or `default_ui.py`.
- **Disposable reference (do not wire into the build):** `ui/Atlas Chat.html`, `ui/app.jsx`, `ui/ui.jsx`, `ui/styles.css` are styling references for a future reskin only.

---

## File Structure

- `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py` — **new.** Generic FastAPI app factory `create_copilotkit_app()`. Sole new Python module. Mirrors `default_ui.py` as a drop-in entry point.
- `src/autobots_devtools_shared_lib/dynagent/ui/__init__.py` — **modify.** Export `create_copilotkit_app`.
- `pyproject.toml` — **modify.** Add `[project.optional-dependencies]` group `copilotkit-ui`.
- `tests/unit/test_copilotkit_server.py` — **new.** One smoke test: the factory builds and mounts the AG-UI route.
- `ui/` — **new Next.js app** (alongside the disposable reference files):
  - `ui/package.json`, `ui/next.config.mjs`, `ui/tsconfig.json`, `ui/.gitignore`, `ui/.env.example`, `ui/next-env.d.ts`
  - `ui/app/api/copilotkit/route.ts` — CopilotRuntime proxy
  - `ui/app/layout.tsx`, `ui/app/page.tsx` — CopilotKit provider + `<CopilotChat>`
  - `ui/README.md` — run + manual-verification runbook

---

### Task 1: Python AG-UI server factory

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`
- Modify: `src/autobots_devtools_shared_lib/dynagent/ui/__init__.py`
- Modify: `pyproject.toml` (add optional dependency group)
- Test: `tests/unit/test_copilotkit_server.py`

**Interfaces:**
- Consumes: `create_base_agent(checkpointer=...) -> CompiledStateGraph` (from `autobots_devtools_shared_lib.dynagent.agents.base_agent`); `get_langfuse_handler() -> CallbackHandler | None` (from `autobots_devtools_shared_lib.common.observability.tracing`); `InMemorySaver` (from `langgraph.checkpoint.memory`).
- Produces: `create_copilotkit_app(agent_name: str = "coordinator", path: str = "/agent") -> fastapi.FastAPI`. Builds the graph with an `InMemorySaver`, injects the Langfuse callback into the graph run config via `.with_config(...)`, wraps it in `LangGraphAgent(name=agent_name, ...)`, registers it with `add_langgraph_fastapi_endpoint(app, agent, path)`, and returns the app. Later tasks (Next.js) rely on the path `"/agent"` and agent name `"coordinator"`.

- [ ] **Step 1: Add the optional dependency group to `pyproject.toml`**

Insert a new `[project.optional-dependencies]` table immediately after the `dev = [ ... ]` array (which ends at line 39, before `[tool.poetry]`). Do not add `ag-ui-langgraph` to the core `dependencies` list.

```toml
[project.optional-dependencies]
copilotkit-ui = [
    "ag-ui-langgraph>=0.0.42",
]
```

- [ ] **Step 2: Write the failing smoke test**

Create `tests/unit/test_copilotkit_server.py`:

```python
# ABOUTME: Smoke test for the generic CopilotKit/AG-UI FastAPI app factory.
# ABOUTME: Confirms create_copilotkit_app builds and mounts the AG-UI route.

from unittest.mock import MagicMock, patch

import pytest


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

    # Built the graph exactly once via the shared factory.
    mock_create_base_agent.assert_called_once()

    # The AG-UI endpoint is registered on the app under the requested path.
    paths = {route.path for route in app.routes}
    assert "/agent" in paths


@patch("autobots_devtools_shared_lib.dynagent.ui.copilotkit_server.create_base_agent")
def test_create_copilotkit_app_default_args(mock_create_base_agent, mock_graph):
    """Defaults mount the coordinator agent at /agent."""
    from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app

    mock_create_base_agent.return_value = mock_graph

    app = create_copilotkit_app()

    paths = {route.path for route in app.routes}
    assert "/agent" in paths
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `make test-one TEST=tests/unit/test_copilotkit_server.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'autobots_devtools_shared_lib.dynagent.ui.copilotkit_server'`.

(If `ag-ui-langgraph` is not yet installed in the shared venv, first install it: `source ../.venv/bin/activate && pip install "ag-ui-langgraph>=0.0.42"`.)

- [ ] **Step 4: Implement `copilotkit_server.py`**

Create `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`:

```python
# ABOUTME: Generic FastAPI AG-UI entry point for dynagent use cases (CopilotKit).
# ABOUTME: Drop-in parallel to default_ui.py — wraps create_base_agent() for a React UI.

from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_handler
from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent

logger = get_logger(__name__)


def create_copilotkit_app(agent_name: str = "coordinator", path: str = "/agent") -> FastAPI:
    """Build a FastAPI app that serves a dynagent graph over the AG-UI protocol.

    Mirrors ``default_ui.py``: consuming domains set ``DYNAGENT_CONFIG_ROOT_DIR``
    (per the existing convention) and call this factory. The browser never talks
    to this server directly — a Next.js CopilotRuntime proxy does.

    Args:
        agent_name: AG-UI agent identifier. Must match the Next.js ``agents`` key
            and the React ``agent`` prop. Defaults to ``"coordinator"``.
        path: FastAPI mount path for the AG-UI endpoint. Defaults to ``"/agent"``.

    Returns:
        A configured FastAPI app with the AG-UI route registered.
    """
    from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

    # Build the graph the same way invoke/stream paths do: shared factory + InMemorySaver.
    graph = create_base_agent(checkpointer=InMemorySaver())  # pyright: ignore[reportCallIssue]

    # Preserve existing Langfuse tracing by injecting the callback into the graph
    # run config — the same handler stream_agent_events / invoke_agent attach.
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler is not None:
        graph = graph.with_config({"callbacks": [langfuse_handler], "recursion_limit": 50})
    else:
        graph = graph.with_config({"recursion_limit": 50})

    agent = LangGraphAgent(
        name=agent_name,
        description="Dynagent multi-agent coordinator served over AG-UI.",
        graph=graph,
    )

    app = FastAPI(title=f"Dynagent AG-UI ({agent_name})")
    add_langgraph_fastapi_endpoint(app, agent, path)

    logger.info(f"Mounted AG-UI agent '{agent_name}' at '{path}'")
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_copilotkit_app(), host="0.0.0.0", port=8000)  # noqa: S104
```

- [ ] **Step 5: Export the factory from the UI subpackage**

Edit `src/autobots_devtools_shared_lib/dynagent/ui/__init__.py` to add the import and `__all__` entry. The file becomes:

```python
# ABOUTME: UI subpackage for the dynagent reference architecture.
# ABOUTME: Shared streaming helpers and a generic Chainlit entry point.

from autobots_devtools_shared_lib.dynagent.ui.copilotkit_server import create_copilotkit_app
from autobots_devtools_shared_lib.dynagent.ui.ui_utils import (
    format_dict_item,
    stream_agent_events,
    structured_to_markdown,
)

__all__ = [
    "create_copilotkit_app",
    "format_dict_item",
    "stream_agent_events",
    "structured_to_markdown",
]
```

> Note: `create_copilotkit_app` imports `ag_ui_langgraph` lazily (inside the function body), so importing the `ui` package does not require the optional `copilotkit-ui` dependency. Keep the `ag_ui_langgraph` import inside the function — do not hoist it to module top level.

- [ ] **Step 6: Run the test to verify it passes**

Run: `make test-one TEST=tests/unit/test_copilotkit_server.py`
Expected: PASS — both tests green.

- [ ] **Step 7: Format, lint, type-check**

Run: `make format && make lint && make type-check`
Expected: no errors. (If pyright flags the `ag_ui_langgraph` import as missing because the optional dep is not installed in the type-check venv, install it first per Step 3.)

- [ ] **Step 8: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py \
        src/autobots_devtools_shared_lib/dynagent/ui/__init__.py \
        tests/unit/test_copilotkit_server.py \
        pyproject.toml
git commit -m "feat(ui): generic CopilotKit/AG-UI FastAPI app factory"
```

---

### Task 2: Next.js reference app

**Files:**
- Create: `ui/package.json`, `ui/next.config.mjs`, `ui/tsconfig.json`, `ui/.gitignore`, `ui/.env.example`, `ui/next-env.d.ts`
- Create: `ui/app/api/copilotkit/route.ts`
- Create: `ui/app/layout.tsx`, `ui/app/page.tsx`

**Interfaces:**
- Consumes: the FastAPI AG-UI endpoint from Task 1 at `http://localhost:8000/agent`, agent name `"coordinator"`.
- Produces: a runnable Next.js app whose `/api/copilotkit` route proxies to FastAPI and whose page renders `<CopilotChat>` bound to `agent="coordinator"`.

- [ ] **Step 1: Create `ui/package.json`**

```json
{
  "name": "dynagent-copilotkit-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@copilotkit/react-core": "^1.10.5",
    "@copilotkit/react-ui": "^1.10.5",
    "@copilotkit/runtime": "^1.10.5",
    "next": "^15.3.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.6.0"
  }
}
```

- [ ] **Step 2: Create `ui/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules", ".venv"]
}
```

- [ ] **Step 3: Create `ui/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {};

export default nextConfig;
```

- [ ] **Step 4: Create `ui/next-env.d.ts`**

```typescript
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

- [ ] **Step 5: Create `ui/.gitignore`**

```gitignore
node_modules/
.next/
.env
.env.local
next-env.d.ts
```

- [ ] **Step 6: Create `ui/.env.example`**

```bash
# URL of the shared-lib FastAPI AG-UI endpoint (Task 1). Includes the /agent path.
LANGGRAPH_DEPLOYMENT_URL=http://localhost:8000/agent
```

- [ ] **Step 7: Create `ui/app/api/copilotkit/route.ts`**

```typescript
import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

// The agent does its own LLM calls, so an empty adapter is correct.
const serviceAdapter = new ExperimentalEmptyAdapter();

const runtime = new CopilotRuntime({
  agents: {
    coordinator: new LangGraphHttpAgent({
      url: process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8000/agent",
    }),
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};
```

- [ ] **Step 8: Create `ui/app/layout.tsx`**

```tsx
import type { ReactNode } from "react";

export const metadata = {
  title: "Dynagent CopilotKit UI",
  description: "React chat UI for Dynagent agents over AG-UI.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 9: Create `ui/app/page.tsx`**

```tsx
"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

export default function Page() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="coordinator">
      <div style={{ height: "100vh" }}>
        <CopilotChat
          labels={{
            title: "Dynagent",
            initial: "Hello, how can I help you today?",
          }}
        />
      </div>
    </CopilotKit>
  );
}
```

- [ ] **Step 10: Install dependencies and type-check the app**

Run:
```bash
cd ui && npm install && npm run typecheck
```
Expected: `npm install` resolves CopilotKit + Next packages; `tsc --noEmit` exits 0 with no type errors. (This is the verification gate for this task; frontend unit/E2E tests are deferred per the spec.)

- [ ] **Step 11: Commit**

```bash
git add ui/package.json ui/package-lock.json ui/next.config.mjs ui/tsconfig.json \
        ui/.gitignore ui/.env.example ui/next-env.d.ts \
        ui/app/api/copilotkit/route.ts ui/app/layout.tsx ui/app/page.tsx
git commit -m "feat(ui): Next.js CopilotKit reference app for AG-UI"
```

---

### Task 3: Runbook + manual verification

**Files:**
- Create: `ui/README.md`

**Interfaces:**
- Consumes: Task 1 (`create_copilotkit_app`) and Task 2 (Next.js app).
- Produces: documented two-process run procedure and the manual verification checklist the spec calls for (streaming, tool-call visibility, structured-output rendering).

- [ ] **Step 1: Create `ui/README.md`**

```markdown
# Dynagent CopilotKit UI (reference app)

React chat UI that streams a Dynagent LangGraph agent via the AG-UI protocol.
Two processes: a Python FastAPI AG-UI server (shared-lib) and this Next.js proxy app.

The legacy `Atlas Chat.html`, `app.jsx`, `ui.jsx`, and `styles.css` files in this
directory are disposable styling references for a future reskin — they are not part
of the build.

## Prerequisites

- The shared venv is set up (`make setup` from `ws-autobots/`).
- The optional UI dependency is installed:
  `source ../.venv/bin/activate && pip install "ag-ui-langgraph>=0.0.42"`
  (or `pip install -e "autobots-devtools-shared-lib[copilotkit-ui]"`).
- `DYNAGENT_CONFIG_ROOT_DIR` is set for the target domain (see repo CLAUDE.md), e.g.
  `export DYNAGENT_CONFIG_ROOT_DIR=configs/bro`.

## Run

Terminal 1 — FastAPI AG-UI server (port 8000, path `/agent`):

```bash
cd autobots-devtools-shared-lib
source ../.venv/bin/activate
python -m autobots_devtools_shared_lib.dynagent.ui.copilotkit_server
```

Terminal 2 — Next.js app (port 3000):

```bash
cd autobots-devtools-shared-lib/ui
cp .env.example .env   # first run only
npm install            # first run only
npm run dev
```

Open http://localhost:3000.

## Manual verification checklist

Send a message that triggers a tool call and a structured response, then confirm:

- [ ] Assistant text streams token-by-token (not all at once).
- [ ] Tool calls are visible in the chat as the agent runs them.
- [ ] Structured output renders as a final assistant message.
- [ ] Stopping the FastAPI server surfaces a clean error in chat (not a blank stream).
```

- [ ] **Step 2: Commit**

```bash
git add ui/README.md
git commit -m "docs(ui): runbook and manual verification checklist for CopilotKit UI"
```

---

## Self-Review

**Spec coverage:**
- Streaming-chat parity (tokens + tool calls + structured output) → AG-UI `LangGraphAgent` wraps the graph (Task 1); manual checklist verifies all three (Task 3). ✅
- Reuse off-the-shelf framework (CopilotKit/AG-UI) → Tasks 1–2. ✅
- Generic + reusable in shared-lib, mirroring `default_ui.py` → `create_copilotkit_app` factory (Task 1). ✅
- Leave graph/tools/config/tracing untouched → only new files; Langfuse callback injected via `.with_config`, no edits to existing modules (Task 1). ✅
- `create_copilotkit_app(agent_name="coordinator")` building graph via `create_base_agent()` + `InMemorySaver` + `add_langgraph_fastapi_endpoint` → Task 1. ✅
- Langfuse callback injected into run config as invoke/stream do → Task 1 Step 4. ✅
- Next.js app: `app/api/copilotkit/route.ts` (CopilotRuntime + LangGraphHttpAgent + ExperimentalEmptyAdapter + `copilotRuntimeNextJSAppRouterEndpoint`), page with `<CopilotKit>`/`<CopilotChat>`, fresh `package.json` → Task 2. ✅
- Optional Python dependency group → Task 1 Step 1. ✅
- One Python smoke test via TestClient/route check → Task 1 Step 2. ✅ (Implemented as a `app.routes` path assertion, which is the stable, dependency-light equivalent.)
- Manual verification of chat flow → Task 3. ✅
- Disposable Atlas files untouched and excluded from build → noted in Global Constraints and `ui/README.md`. ✅
- Non-goals (file uploads, generative UI, persistent checkpointer, Atlas reskin, contract/frontend/E2E tests) → not built. ✅

**Type consistency:** Agent name `"coordinator"`, path `"/agent"`, and env var `LANGGRAPH_DEPLOYMENT_URL` (`http://localhost:8000/agent`) are consistent across `copilotkit_server.py`, the smoke test, `route.ts`, `page.tsx`, and the runbook. Factory signature `create_copilotkit_app(agent_name="coordinator", path="/agent")` matches its call sites and exports.

**Note for the implementer (verify during Task 3 manual run):** `graph.with_config(...)` returns a `RunnableBinding` wrapping the compiled graph. `LangGraphAgent` consumes the graph via `astream_events`, which a `RunnableBinding` supports. If a given `ag-ui-langgraph` version requires a bare `CompiledStateGraph` at registration, fall back to passing `graph` un-wrapped and attaching the Langfuse handler another way (e.g. via `LangGraphAgent`'s run config) — confirm Langfuse traces appear during manual verification.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-22-react-copilotkit-ui-integration.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
