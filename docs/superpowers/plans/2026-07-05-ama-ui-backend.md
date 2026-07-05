# AMA UI Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python backend contract (AG-UI streaming plane + client-agnostic REST resource plane) that the Dynagent AMA React UI consumes, wired concretely into `autobots-agents-mer`'s AMA domain over Postgres.

**Architecture:** Two planes share one `create_base_deepagent` graph + one checkpointer. The **streaming plane** (`ui/`) mounts CopilotKit AG-UI at `/agent` and injects the derived activity rail via `STATE_DELTA`. The **resource plane** (`api/`) is plain FastAPI routers (`/threads`, `/skills`, `/tools`, `/mcp-servers`) that import nothing from CopilotKit/AG-UI, backed by `ThreadStore`/`PrefsStore` Protocols. shared-lib defines the framework (Protocols, routers, composition); mer supplies the Postgres implementations, identity resolution, and the concrete app.

**Tech Stack:** Python 3.12+, FastAPI, LangGraph (deepagents engine), CopilotKit/AG-UI (`ag_ui`, `ag_ui_langgraph`, `copilotkit`), SQLModel/SQLAlchemy over Postgres, pytest (`asyncio_mode="auto"`), FastAPI `TestClient`.

## Global Constraints

- **Python:** 3.12+.
- **Formatter/Linter:** Ruff, line-length 100, double quotes. Rules E, W, F, I, B, C4, UP, ARG, SIM, S, TCH, PTH, RET, TRY, PERF, RUF (ignore S101, E501, TRY003).
- **Type checker:** Pyright basic mode.
- **File headers:** Every new source file starts with two `# ABOUTME:` comment lines.
- **Logging:** Use `from autobots_devtools_shared_lib.common.observability import get_logger` (never `print`).
- **Resource plane is client-agnostic:** modules under `dynagent/api/` MUST NOT import `copilotkit`, `ag_ui`, or `ag_ui_langgraph`.
- **Introspection degrades, never 500s:** `/skills`, `/tools`, `/mcp-servers` return an empty-but-valid payload + `warnings: [...]` on backend/MCP failure.
- **Streaming projection is best-effort:** a failure in the activity-rail projection drops the delta but never kills the token stream.
- **Identity:** every resource endpoint and thread is scoped to a `user_id`, resolved via an injected FastAPI dependency (`user_id_dependency`).
- **Test isolation:** put ALL new tests in NEW files. Do NOT fold assertions into modules carrying shared-lib's ~43 known pre-existing unit failures. New tests must pass standalone.
- **CopilotKit/AG-UI imports are lazy:** import them inside functions (not at module top) so resource-plane and non-UI code paths never require them; tests use `pytest.importorskip("copilotkit")`.

---

## File Structure

**shared-lib** — `src/autobots_devtools_shared_lib/dynagent/`

| File | Responsibility |
|---|---|
| `api/__init__.py` | Package marker. |
| `api/thread_store.py` | `ThreadRecord` TypedDict, `ThreadStore`/`PrefsStore` Protocols, `ThreadNotFoundError`/`ThreadAccessError`. |
| `api/skills_discovery.py` | `SkillInfo` TypedDict, `discover_skills(meta, backend)` wrapping deepagents' loader. |
| `api/resources/__init__.py` | Package marker. |
| `api/resources/threads.py` | `thread_group()` helper + `build_threads_router(...)`. |
| `api/resources/skills.py` | `build_skills_router(...)` (list merged with prefs + PATCH pref). |
| `api/resources/tools.py` | `tool_access()`, `group_mcp_tools()` helpers + `build_tools_router(...)`. |
| `api/resources/mcp_servers.py` | `server_abbr()` helper + `build_mcp_servers_router(...)`. |
| `api/router.py` | `build_resource_router(...)` composing the four + `register_exception_handlers(app)`. |
| `ui/rail_stream.py` | (MODIFY) best-effort projection guard + `on_run_finished` touch hook. |
| `ui/agui_endpoint.py` | `mount_agui_endpoint(...)` — builds `RailAGUIAgent`, mounts `/agent`. |
| `ui/agui_app.py` | `create_agui_app(...)` — resource router + AG-UI endpoint + `/health`. |
| `ui/copilotkit_server.py` | **DELETE** (spike; good parts fold into `agui_app.py`). |

**mer** — `src/autobots_agents_mer/`

| File | Responsibility |
|---|---|
| `common/db/models_ama.py` | `AmaThreadEntity` + `AmaUserPrefEntity` SQLModel tables. |
| `common/db/engine.py` | (MODIFY) import the two new models so `create_all` registers them. |
| `domains/ama/web/__init__.py` | Package marker. |
| `domains/ama/web/thread_store_pg.py` | `PgThreadStore` + `PgPrefsStore` (SQLAlchemy). |
| `domains/ama/web/identity.py` | `resolve_user_id(request)` layered dependency. |
| `domains/ama/web/app.py` | Concrete app: stores + checkpointer + backend + identity → `create_agui_app(...)`. |
| `sbin/run_ama_web.sh` | Launch uvicorn on port 8001, parallel to Chainlit (3340). |

**Tests** (all NEW files)

- shared-lib: `tests/unit/test_thread_store_protocols.py`, `test_resource_threads.py`, `test_skills_discovery.py`, `test_resource_skills.py`, `test_resource_tools.py`, `test_resource_mcp_servers.py`, `test_resource_router.py`, `test_rail_stream_touch.py`, `test_agui_endpoint.py`, `test_agui_app.py`.
- mer: `tests/integration/domains/ama/test_thread_store_pg.py`, `tests/unit/domains/test_ama_identity.py`.

---

## Task 1: Thread/Prefs Protocols + domain errors

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/__init__.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/api/thread_store.py`
- Test: `tests/unit/test_thread_store_protocols.py`

**Interfaces:**
- Produces:
  - `ThreadRecord = TypedDict("ThreadRecord", {id:str, user_id:str, title:str, created_at:datetime, updated_at:datetime})`
  - `class ThreadStore(Protocol)` with async `list(user_id, q=None)->list[ThreadRecord]`, `create(user_id, title="New chat")->ThreadRecord`, `get(thread_id)->ThreadRecord|None`, `rename(thread_id, title)->None`, `delete(thread_id)->None`, `touch(thread_id)->None`.
  - `class PrefsStore(Protocol)` with async `get(user_id, namespace)->dict[str,bool]`, `set(user_id, namespace, key, value)->None`.
  - `class ThreadNotFoundError(Exception)`, `class ThreadAccessError(Exception)`.

- [ ] **Step 1: Create the package marker**

Create `src/autobots_devtools_shared_lib/dynagent/api/__init__.py`:

```python
# ABOUTME: Client-agnostic resource plane for the dynagent UI backend.
# ABOUTME: Plain FastAPI routers + store Protocols; no CopilotKit/AG-UI imports.
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_thread_store_protocols.py`:

```python
# ABOUTME: Unit tests for the ThreadStore/PrefsStore Protocols and domain errors.
# ABOUTME: A dict-backed fake must structurally satisfy the Protocols.

from datetime import UTC, datetime


def test_fake_satisfies_thread_store_protocol():
    from autobots_devtools_shared_lib.dynagent.api.thread_store import (
        ThreadRecord,
        ThreadStore,
    )

    class FakeThreadStore:
        def __init__(self) -> None:
            self._rows: dict[str, ThreadRecord] = {}

        async def list(self, user_id: str, q: str | None = None) -> list[ThreadRecord]:
            return [r for r in self._rows.values() if r["user_id"] == user_id]

        async def create(self, user_id: str, title: str = "New chat") -> ThreadRecord:
            now = datetime.now(UTC)
            rec: ThreadRecord = {
                "id": "t1",
                "user_id": user_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }
            self._rows[rec["id"]] = rec
            return rec

        async def get(self, thread_id: str) -> ThreadRecord | None:
            return self._rows.get(thread_id)

        async def rename(self, thread_id: str, title: str) -> None:
            self._rows[thread_id]["title"] = title

        async def delete(self, thread_id: str) -> None:
            self._rows.pop(thread_id, None)

        async def touch(self, thread_id: str) -> None:
            self._rows[thread_id]["updated_at"] = datetime.now(UTC)

    store: ThreadStore = FakeThreadStore()
    assert isinstance(store, ThreadStore)


def test_fake_satisfies_prefs_store_protocol():
    from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore

    class FakePrefsStore:
        def __init__(self) -> None:
            self._kv: dict[tuple[str, str, str], bool] = {}

        async def get(self, user_id: str, namespace: str) -> dict[str, bool]:
            return {k[2]: v for k, v in self._kv.items() if k[0] == user_id and k[1] == namespace}

        async def set(self, user_id: str, namespace: str, key: str, value: bool) -> None:
            self._kv[(user_id, namespace, key)] = value

    store: PrefsStore = FakePrefsStore()
    assert isinstance(store, PrefsStore)


def test_domain_errors_are_exceptions():
    from autobots_devtools_shared_lib.dynagent.api.thread_store import (
        ThreadAccessError,
        ThreadNotFoundError,
    )

    assert issubclass(ThreadNotFoundError, Exception)
    assert issubclass(ThreadAccessError, Exception)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_thread_store_protocols.py -v`
Expected: FAIL — `ModuleNotFoundError: ...dynagent.api.thread_store`

- [ ] **Step 4: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/api/thread_store.py`:

```python
# ABOUTME: DB-agnostic Protocols for the AMA thread index and per-user UI prefs.
# ABOUTME: mer implements these over Postgres; shared-lib tests use dict-backed fakes.

from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypedDict, runtime_checkable


class ThreadRecord(TypedDict):
    """Left-rail metadata for one conversation. Never holds message content."""

    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@runtime_checkable
class ThreadStore(Protocol):
    """Index of conversations (left rail). Content lives in the checkpointer."""

    async def list(self, user_id: str, q: str | None = None) -> list[ThreadRecord]: ...

    async def create(self, user_id: str, title: str = "New chat") -> ThreadRecord: ...

    async def get(self, thread_id: str) -> ThreadRecord | None: ...

    async def rename(self, thread_id: str, title: str) -> None: ...

    async def delete(self, thread_id: str) -> None: ...

    async def touch(self, thread_id: str) -> None: ...


@runtime_checkable
class PrefsStore(Protocol):
    """Narrow per-user KV for display-only UI prefs (namespace = 'skills' | 'mcp')."""

    async def get(self, user_id: str, namespace: str) -> dict[str, bool]: ...

    async def set(self, user_id: str, namespace: str, key: str, value: bool) -> None: ...


class ThreadNotFoundError(Exception):
    """Raised when a thread_id has no metadata row."""


class ThreadAccessError(Exception):
    """Raised when a user_id does not own the requested thread."""
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_thread_store_protocols.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/__init__.py \
        src/autobots_devtools_shared_lib/dynagent/api/thread_store.py \
        tests/unit/test_thread_store_protocols.py
git commit -m "feat(dynagent-api): ThreadStore/PrefsStore Protocols + domain errors"
```

---

## Task 2: Threads resource router (CRUD + grouping)

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/resources/__init__.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/api/resources/threads.py`
- Test: `tests/unit/test_resource_threads.py`

**Interfaces:**
- Consumes: `ThreadStore`, `ThreadRecord`, `ThreadNotFoundError`, `ThreadAccessError` from Task 1.
- Produces:
  - `def thread_group(updated_at: datetime, *, now: datetime | None = None) -> str` — returns `"Today"` or `"Earlier"`.
  - `def build_threads_router(thread_store: ThreadStore, user_id_dependency: Callable[..., str] | Callable[..., Awaitable[str]], checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None) -> APIRouter`.
  - Routes: `GET /threads` → `list[{id,title,group,updated_at}]`; `POST /threads` → `{"id": str}`; `PATCH /threads/{id}` → `{"ok": True}`; `DELETE /threads/{id}` → `{"ok": True}`.

- [ ] **Step 1: Create the package marker**

Create `src/autobots_devtools_shared_lib/dynagent/api/resources/__init__.py`:

```python
# ABOUTME: FastAPI APIRouters for the client-agnostic resource plane.
# ABOUTME: threads (stateful) + skills/tools/mcp-servers (introspection-only).
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_resource_threads.py`:

```python
# ABOUTME: TestClient coverage for the threads CRUD router against a dict-backed fake.
# ABOUTME: Covers list/grouping, create, rename, delete+checkpoint clear, 404/403.

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autobots_devtools_shared_lib.dynagent.api.resources.threads import (
    build_threads_router,
    thread_group,
)
from autobots_devtools_shared_lib.dynagent.api.router import register_exception_handlers
from autobots_devtools_shared_lib.dynagent.api.thread_store import ThreadRecord


class FakeThreadStore:
    def __init__(self) -> None:
        self.rows: dict[str, ThreadRecord] = {}

    async def list(self, user_id, q=None):
        rows = [r for r in self.rows.values() if r["user_id"] == user_id]
        if q:
            rows = [r for r in rows if q.lower() in r["title"].lower()]
        return sorted(rows, key=lambda r: r["updated_at"], reverse=True)

    async def create(self, user_id, title="New chat"):
        now = datetime.now(UTC)
        rec: ThreadRecord = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        self.rows[rec["id"]] = rec
        return rec

    async def get(self, thread_id):
        return self.rows.get(thread_id)

    async def rename(self, thread_id, title):
        self.rows[thread_id]["title"] = title

    async def delete(self, thread_id):
        self.rows.pop(thread_id, None)

    async def touch(self, thread_id):
        self.rows[thread_id]["updated_at"] = datetime.now(UTC)


@pytest.fixture
def deleted_checkpoints():
    return []


@pytest.fixture
def client(deleted_checkpoints):
    store = FakeThreadStore()

    async def checkpoint_deleter(thread_id: str) -> None:
        deleted_checkpoints.append(thread_id)

    app = FastAPI()
    register_exception_handlers(app)
    app.state.store = store
    app.include_router(
        build_threads_router(
            store, user_id_dependency=lambda: "u1", checkpoint_deleter=checkpoint_deleter
        )
    )
    return TestClient(app)


def test_thread_group_today_vs_earlier():
    now = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)
    assert thread_group(now, now=now) == "Today"
    assert thread_group(now - timedelta(days=2), now=now) == "Earlier"


def test_create_then_list_groups_today(client):
    created = client.post("/threads", json={}).json()
    assert "id" in created
    listed = client.get("/threads").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["title"] == "New chat"
    assert listed[0]["group"] == "Today"


def test_rename_updates_title(client):
    tid = client.post("/threads", json={}).json()["id"]
    resp = client.patch(f"/threads/{tid}", json={"title": "Renamed"})
    assert resp.status_code == 200
    assert client.get("/threads").json()[0]["title"] == "Renamed"


def test_delete_clears_metadata_and_checkpoint(client, deleted_checkpoints):
    tid = client.post("/threads", json={}).json()["id"]
    resp = client.delete(f"/threads/{tid}")
    assert resp.status_code == 200
    assert client.get("/threads").json() == []
    assert deleted_checkpoints == [tid]


def test_rename_unknown_thread_404(client):
    assert client.patch("/threads/does-not-exist", json={"title": "x"}).status_code == 404


def test_rename_empty_title_422(client):
    tid = client.post("/threads", json={}).json()["id"]
    assert client.patch(f"/threads/{tid}", json={"title": ""}).status_code == 422


def test_cross_user_delete_403():
    store = FakeThreadStore()

    owner_app = FastAPI()
    register_exception_handlers(owner_app)
    owner_app.include_router(build_threads_router(store, user_id_dependency=lambda: "owner"))
    rec = TestClient(owner_app).post("/threads", json={}).json()  # thread owned by "owner"

    intruder_app = FastAPI()
    register_exception_handlers(intruder_app)
    intruder_app.include_router(
        build_threads_router(store, user_id_dependency=lambda: "intruder")
    )
    assert TestClient(intruder_app).delete(f"/threads/{rec['id']}").status_code == 403
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_resource_threads.py -v`
Expected: FAIL — `ModuleNotFoundError: ...api.resources.threads` (and `...api.router`).

- [ ] **Step 4: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/api/resources/threads.py`:

```python
# ABOUTME: /threads router — the only stateful, per-user resource surface.
# ABOUTME: Metadata-only CRUD over ThreadStore; DELETE also clears checkpoint state.

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from autobots_devtools_shared_lib.dynagent.api.thread_store import (
    ThreadAccessError,
    ThreadNotFoundError,
    ThreadStore,
)


def thread_group(updated_at: datetime, *, now: datetime | None = None) -> str:
    """Bucket a thread into 'Today' or 'Earlier' by UTC calendar date."""
    ref = now or datetime.now(UTC)
    return "Today" if updated_at.date() == ref.date() else "Earlier"


class _CreateBody(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=200)


class _RenameBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)


async def _require_owned(store: ThreadStore, thread_id: str, user_id: str) -> None:
    record = await store.get(thread_id)
    if record is None:
        raise ThreadNotFoundError(thread_id)
    if record["user_id"] != user_id:
        raise ThreadAccessError(thread_id)


def build_threads_router(
    thread_store: ThreadStore,
    user_id_dependency: Callable[..., Any],
    checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None,
) -> APIRouter:
    """Build the /threads CRUD router bound to a store + identity dependency."""
    router = APIRouter(prefix="/threads", tags=["threads"])

    @router.get("")
    async def list_threads(
        q: str | None = None, user_id: str = Depends(user_id_dependency)
    ) -> list[dict[str, Any]]:
        records = await thread_store.list(user_id, q)
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "group": thread_group(r["updated_at"]),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in records
        ]

    @router.post("")
    async def create_thread(
        body: _CreateBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, str]:
        record = await thread_store.create(user_id, body.title)
        return {"id": record["id"]}

    @router.patch("/{thread_id}")
    async def rename_thread(
        thread_id: str, body: _RenameBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await _require_owned(thread_store, thread_id, user_id)
        await thread_store.rename(thread_id, body.title)
        return {"ok": True}

    @router.delete("/{thread_id}")
    async def delete_thread(
        thread_id: str, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await _require_owned(thread_store, thread_id, user_id)
        await thread_store.delete(thread_id)
        if checkpoint_deleter is not None:
            await checkpoint_deleter(thread_id)
        return {"ok": True}

    return router
```

Note: `build_threads_router` references `ThreadNotFoundError`/`ThreadAccessError` which the app maps to 404/403 via `register_exception_handlers` (Task 7). This test imports `register_exception_handlers` from `api.router`, so create a minimal stub now and complete it in Task 7.

- [ ] **Step 5: Add the minimal exception-handler stub (completed in Task 7)**

Create `src/autobots_devtools_shared_lib/dynagent/api/router.py` (stub — full compose in Task 7):

```python
# ABOUTME: Composes the resource-plane routers and registers domain->HTTP error mapping.
# ABOUTME: build_resource_router() mounts threads/skills/tools/mcp-servers under one router.

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autobots_devtools_shared_lib.dynagent.api.thread_store import (
    ThreadAccessError,
    ThreadNotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Map store-layer domain errors to typed JSON HTTP responses."""

    @app.exception_handler(ThreadNotFoundError)
    async def _not_found(_request: Request, exc: ThreadNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"thread not found: {exc}"})

    @app.exception_handler(ThreadAccessError)
    async def _forbidden(_request: Request, exc: ThreadAccessError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": f"forbidden: {exc}"})
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_resource_threads.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/resources/__init__.py \
        src/autobots_devtools_shared_lib/dynagent/api/resources/threads.py \
        src/autobots_devtools_shared_lib/dynagent/api/router.py \
        tests/unit/test_resource_threads.py
git commit -m "feat(dynagent-api): threads CRUD router with grouping + checkpoint clear"
```

---

## Task 3: Skills discovery helper

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/skills_discovery.py`
- Test: `tests/unit/test_skills_discovery.py`

**Interfaces:**
- Consumes: `AgentMeta` (`.skills_map: dict[str, list[str]]`), a deepagents backend, and deepagents' `_alist_skills_with_errors(backend, source_path) -> tuple[list[SkillMetadata], str | None]`.
- Produces:
  - `SkillInfo = TypedDict("SkillInfo", {name:str, description:str, category:str|None, enabled:bool})`.
  - `async def discover_skills(meta, backend) -> tuple[list[SkillInfo], list[str]]` — union of every source path across `meta.skills_map`, deduped **last-wins by name**, `enabled` defaulting `True`, `category` from `SkillMetadata["metadata"].get("category")`, plus aggregated `warnings`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_skills_discovery.py`:

```python
# ABOUTME: Unit tests for discover_skills mapping, last-wins dedupe, and warnings.
# ABOUTME: Monkeypatches deepagents' _alist_skills_with_errors — no real backend needed.

from types import SimpleNamespace

import pytest


def _skill(name, desc, category=None):
    return {
        "name": name,
        "description": desc,
        "path": f"/skills/{name}/SKILL.md",
        "metadata": {"category": category} if category else {},
        "license": None,
        "compatibility": None,
        "allowed_tools": [],
    }


@pytest.mark.asyncio
async def test_maps_and_dedupes_last_wins(monkeypatch):
    import autobots_devtools_shared_lib.dynagent.api.skills_discovery as mod

    async def fake_loader(_backend, source_path):
        if source_path == "/skills/base/":
            return [_skill("alpha", "old alpha", "core"), _skill("beta", "beta desc")], None
        return [_skill("alpha", "new alpha", "core")], None

    monkeypatch.setattr(mod, "_alist_skills_with_errors", fake_loader)

    meta = SimpleNamespace(skills_map={"assistant": ["/skills/base/", "/skills/user/"]})
    skills, warnings = await mod.discover_skills(meta, backend=object())

    by_name = {s["name"]: s for s in skills}
    assert by_name["alpha"]["description"] == "new alpha"  # last source wins
    assert by_name["alpha"]["category"] == "core"
    assert by_name["alpha"]["enabled"] is True
    assert by_name["beta"]["category"] is None
    assert warnings == []


@pytest.mark.asyncio
async def test_aggregates_source_warnings(monkeypatch):
    import autobots_devtools_shared_lib.dynagent.api.skills_discovery as mod

    async def fake_loader(_backend, source_path):
        return [], f"Cannot load skills from '{source_path}': boom"

    monkeypatch.setattr(mod, "_alist_skills_with_errors", fake_loader)
    meta = SimpleNamespace(skills_map={"assistant": ["/skills/"]})
    skills, warnings = await mod.discover_skills(meta, backend=object())

    assert skills == []
    assert warnings == ["Cannot load skills from '/skills/': boom"]


@pytest.mark.asyncio
async def test_dedupes_source_paths_across_roster(monkeypatch):
    import autobots_devtools_shared_lib.dynagent.api.skills_discovery as mod

    seen: list[str] = []

    async def fake_loader(_backend, source_path):
        seen.append(source_path)
        return [], None

    monkeypatch.setattr(mod, "_alist_skills_with_errors", fake_loader)
    meta = SimpleNamespace(
        skills_map={"assistant": ["/skills/"], "wiring-check": ["/skills/"]}
    )
    await mod.discover_skills(meta, backend=object())
    assert seen == ["/skills/"]  # deduped, loaded once
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_skills_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError: ...api.skills_discovery`

- [ ] **Step 3: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/api/skills_discovery.py`:

```python
# ABOUTME: Live skills discovery for /skills — wraps deepagents' own loader.
# ABOUTME: Calls the loader live (not off checkpoint state) to sidestep durable staleness.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from deepagents.middleware.skills import _alist_skills_with_errors

from autobots_devtools_shared_lib.common.observability import get_logger

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta

logger = get_logger(__name__)


class SkillInfo(TypedDict):
    """One skill as surfaced to the left rail. `enabled` is a UI pref, merged later."""

    name: str
    description: str
    category: str | None
    enabled: bool


def _ordered_unique_sources(meta: AgentMeta) -> list[str]:
    """Union every source path across the roster, preserving first-seen order."""
    seen: list[str] = []
    for sources in meta.skills_map.values():
        for source_path in sources:
            if source_path not in seen:
                seen.append(source_path)
    return seen


async def discover_skills(meta: AgentMeta, backend: Any) -> tuple[list[SkillInfo], list[str]]:
    """Load skills live via deepagents' loader, deduped last-wins, with warnings.

    Isolated behind this helper so a future swap to a public deepagents API is one line.
    """
    by_name: dict[str, SkillInfo] = {}
    warnings: list[str] = []
    for source_path in _ordered_unique_sources(meta):
        try:
            found, source_error = await _alist_skills_with_errors(backend, source_path)
        except Exception as exc:  # degrade, never 500
            logger.warning("skills discovery failed for %s: %s", source_path, exc)
            warnings.append(f"Cannot load skills from '{source_path}': {exc}")
            continue
        if source_error is not None:
            warnings.append(source_error)
        for skill in found:
            by_name[skill["name"]] = SkillInfo(
                name=skill["name"],
                description=skill["description"],
                category=(skill.get("metadata") or {}).get("category"),
                enabled=True,
            )
    return list(by_name.values()), warnings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_skills_discovery.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/skills_discovery.py \
        tests/unit/test_skills_discovery.py
git commit -m "feat(dynagent-api): discover_skills live loader wrapper with dedupe+warnings"
```

---

## Task 4: Skills resource router

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/resources/skills.py`
- Test: `tests/unit/test_resource_skills.py`

**Interfaces:**
- Consumes: `discover_skills` (Task 3), `SkillInfo` (Task 3), `PrefsStore` (Task 1), `AgentMeta`, a backend, `user_id_dependency`.
- Produces:
  - `def build_skills_router(meta, backend, prefs_store: PrefsStore, user_id_dependency) -> APIRouter`.
  - Routes: `GET /skills` → `{"skills": list[SkillInfo], "warnings": list[str]}` (enabled merged from prefs namespace `"skills"`, default on); `PATCH /skills/{name}` body `{"enabled": bool}` → `{"ok": True}`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_resource_skills.py`:

```python
# ABOUTME: TestClient coverage for the /skills router: list merged with prefs + PATCH.
# ABOUTME: discover_skills is monkeypatched; a dict-backed PrefsStore drives enabled state.

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.skills as skills_mod
from autobots_devtools_shared_lib.dynagent.api.resources.skills import build_skills_router


class FakePrefs:
    def __init__(self) -> None:
        self.kv: dict[tuple[str, str, str], bool] = {}

    async def get(self, user_id, namespace):
        return {k[2]: v for k, v in self.kv.items() if k[0] == user_id and k[1] == namespace}

    async def set(self, user_id, namespace, key, value):
        self.kv[(user_id, namespace, key)] = value


@pytest.fixture
def prefs():
    return FakePrefs()


@pytest.fixture
def client(monkeypatch, prefs):
    async def fake_discover(_meta, _backend):
        return (
            [
                {"name": "web-research", "description": "research", "category": "core", "enabled": True},
                {"name": "demo-fact", "description": "facts", "category": None, "enabled": True},
            ],
            ["a warning"],
        )

    monkeypatch.setattr(skills_mod, "discover_skills", fake_discover)
    app = FastAPI()
    app.include_router(
        build_skills_router(
            meta=SimpleNamespace(skills_map={}),
            backend=object(),
            prefs_store=prefs,
            user_id_dependency=lambda: "u1",
        )
    )
    return TestClient(app)


def test_list_skills_returns_skills_and_warnings(client):
    body = client.get("/skills").json()
    names = {s["name"] for s in body["skills"]}
    assert names == {"web-research", "demo-fact"}
    assert body["warnings"] == ["a warning"]
    assert all(s["enabled"] for s in body["skills"])


def test_pref_disables_skill(client, prefs):
    prefs.kv[("u1", "skills", "demo-fact")] = False
    body = client.get("/skills").json()
    by_name = {s["name"]: s for s in body["skills"]}
    assert by_name["demo-fact"]["enabled"] is False
    assert by_name["web-research"]["enabled"] is True


def test_patch_sets_pref(client, prefs):
    resp = client.patch("/skills/demo-fact", json={"enabled": False})
    assert resp.status_code == 200
    assert prefs.kv[("u1", "skills", "demo-fact")] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_resource_skills.py -v`
Expected: FAIL — `ModuleNotFoundError: ...api.resources.skills`

- [ ] **Step 3: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/api/resources/skills.py`:

```python
# ABOUTME: /skills router — lists live-loaded skills merged with per-user enabled prefs.
# ABOUTME: PATCH sets a UI-only pref; it does NOT gate agent behavior this cycle.

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from autobots_devtools_shared_lib.dynagent.api.skills_discovery import discover_skills
from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore

_NAMESPACE = "skills"


class _EnabledBody(BaseModel):
    enabled: bool


def build_skills_router(
    meta: Any,
    backend: Any,
    prefs_store: PrefsStore,
    user_id_dependency: Any,
) -> APIRouter:
    """Build the /skills router (list + enable/disable pref)."""
    router = APIRouter(prefix="/skills", tags=["skills"])

    @router.get("")
    async def list_skills(user_id: str = Depends(user_id_dependency)) -> dict[str, Any]:
        skills, warnings = await discover_skills(meta, backend)
        prefs = await prefs_store.get(user_id, _NAMESPACE)
        merged = [{**s, "enabled": prefs.get(s["name"], s["enabled"])} for s in skills]
        return {"skills": merged, "warnings": warnings}

    @router.patch("/{name}")
    async def set_skill_enabled(
        name: str, body: _EnabledBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await prefs_store.set(user_id, _NAMESPACE, name, body.enabled)
        return {"ok": True}

    return router
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_resource_skills.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/resources/skills.py \
        tests/unit/test_resource_skills.py
git commit -m "feat(dynagent-api): /skills router merging live discovery with prefs"
```

---

## Task 5: Tools introspection router

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/resources/tools.py`
- Test: `tests/unit/test_resource_tools.py`

**Interfaces:**
- Consumes: `AgentMeta` (`.mcp_servers_config: dict[str, dict]`), `load_mcp_tools(server_names, servers_config) -> list[Any]` from `dynagent.agents.deep_mcp`.
- Produces:
  - `def tool_access(name: str) -> str` — `"WRITE"` if the (prefix-stripped) tool name contains a write verb, else `"READ"`.
  - `def group_mcp_tools(meta) -> tuple[list[dict], list[str]]` — one `{server, tools:[{name,description,params,access}]}` per server, degrading per-server to `warnings`.
  - `def build_tools_router(meta) -> APIRouter` — `GET /tools` → `{"servers": [...], "warnings": [...]}`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_resource_tools.py`:

```python
# ABOUTME: Unit tests for the /tools access heuristic, grouping, and degrade path.
# ABOUTME: load_mcp_tools is monkeypatched with fake tool objects (no real MCP server).

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.tools as tools_mod
from autobots_devtools_shared_lib.dynagent.api.resources.tools import (
    build_tools_router,
    tool_access,
)


class FakeTool:
    def __init__(self, name, description="", args=None):
        self.name = name
        self.description = description
        self.args = args or {}


@pytest.mark.parametrize(
    "name,expected",
    [
        ("github__get_issue", "READ"),
        ("github__create_issue", "WRITE"),
        ("github__list_repos", "READ"),
        ("jira__update_ticket", "WRITE"),
        ("jira__delete_board", "WRITE"),
        ("search", "READ"),
    ],
)
def test_tool_access_heuristic(name, expected):
    assert tool_access(name) == expected


def test_group_mcp_tools_groups_by_server(monkeypatch):
    def fake_load(server_names, _config):
        (server,) = server_names
        return [FakeTool(f"{server}__get_x", "reads x", {"id": {}})]

    monkeypatch.setattr(tools_mod, "load_mcp_tools", fake_load)
    meta = SimpleNamespace(mcp_servers_config={"github": {}, "jira": {}})
    servers, warnings = tools_mod.group_mcp_tools(meta)
    names = {s["server"] for s in servers}
    assert names == {"github", "jira"}
    gh = next(s for s in servers if s["server"] == "github")
    assert gh["tools"][0]["name"] == "get_x"
    assert gh["tools"][0]["params"] == ["id"]
    assert gh["tools"][0]["access"] == "READ"
    assert warnings == []


def test_group_mcp_tools_degrades_on_unreachable_server(monkeypatch):
    def fake_load(server_names, _config):
        (server,) = server_names
        if server == "broken":
            raise RuntimeError("connection refused")
        return [FakeTool(f"{server}__ok")]

    monkeypatch.setattr(tools_mod, "load_mcp_tools", fake_load)
    meta = SimpleNamespace(mcp_servers_config={"good": {}, "broken": {}})
    servers, warnings = tools_mod.group_mcp_tools(meta)
    good = next(s for s in servers if s["server"] == "good")
    broken = next(s for s in servers if s["server"] == "broken")
    assert good["tools"][0]["name"] == "ok"
    assert broken["tools"] == []
    assert any("broken" in w for w in warnings)


def test_tools_endpoint_empty_config_returns_empty(monkeypatch):
    meta = SimpleNamespace(mcp_servers_config={})
    app = FastAPI()
    app.include_router(build_tools_router(meta))
    body = TestClient(app).get("/tools").json()
    assert body == {"servers": [], "warnings": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_resource_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: ...api.resources.tools`

- [ ] **Step 3: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/api/resources/tools.py`:

```python
# ABOUTME: /tools router — enumerates MCP tools grouped by server, degrading gracefully.
# ABOUTME: access READ/WRITE is a write-verb name heuristic (annotations are a later drop-in).

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.agents.deep_mcp import load_mcp_tools

logger = get_logger(__name__)

_WRITE_VERBS = frozenset(
    {
        "create",
        "update",
        "delete",
        "write",
        "set",
        "put",
        "post",
        "patch",
        "remove",
        "insert",
        "add",
        "send",
        "modify",
        "edit",
    }
)


def _short(name: str) -> str:
    """Strip the '<server>__' MCP prefix for display."""
    return name.split("__", 1)[1] if "__" in name else name


def tool_access(name: str) -> str:
    """Classify a tool as WRITE when any '_'-delimited token is a write verb, else READ."""
    tokens = _short(name).lower().replace("-", "_").split("_")
    return "WRITE" if any(token in _WRITE_VERBS for token in tokens) else "READ"


def _describe_tool(tool: Any) -> dict[str, Any]:
    name = getattr(tool, "name", "")
    args = getattr(tool, "args", None) or {}
    return {
        "name": _short(name),
        "description": getattr(tool, "description", "") or "",
        "params": list(args.keys()),
        "access": tool_access(name),
    }


def group_mcp_tools(meta: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """List MCP tools per server. One bad server yields an empty list + a warning."""
    servers: list[dict[str, Any]] = []
    warnings: list[str] = []
    for server in meta.mcp_servers_config:
        try:
            tools = load_mcp_tools([server], meta.mcp_servers_config)
            servers.append({"server": server, "tools": [_describe_tool(t) for t in tools]})
        except Exception as exc:  # degrade, never 500
            logger.warning("tools introspection failed for %s: %s", server, exc)
            servers.append({"server": server, "tools": []})
            warnings.append(f"Cannot load tools from '{server}': {exc}")
    return servers, warnings


def build_tools_router(meta: Any) -> APIRouter:
    """Build the /tools router (introspection-only)."""
    router = APIRouter(prefix="/tools", tags=["tools"])

    @router.get("")
    async def list_tools() -> dict[str, Any]:
        servers, warnings = group_mcp_tools(meta)
        return {"servers": servers, "warnings": warnings}

    return router
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_resource_tools.py -v`
Expected: PASS (9 tests — 6 parametrized + 3)

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/resources/tools.py \
        tests/unit/test_resource_tools.py
git commit -m "feat(dynagent-api): /tools router with READ/WRITE heuristic + degrade path"
```

---

## Task 6: MCP servers resource router

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/resources/mcp_servers.py`
- Test: `tests/unit/test_resource_mcp_servers.py`

**Interfaces:**
- Consumes: `AgentMeta` (`.mcp_servers_config`), `group_mcp_tools` (Task 5) for `tool_count`, `PrefsStore` (Task 1), `user_id_dependency`.
- Produces:
  - `def server_abbr(name: str) -> str` — 2-char uppercase abbreviation.
  - `def build_mcp_servers_router(meta, prefs_store, user_id_dependency) -> APIRouter` — `GET /mcp-servers` → `{"servers": [{name, abbr, connected, tool_count}]}`; `PATCH /mcp-servers/{name}` body `{"connected": bool}` → `{"ok": True}`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_resource_mcp_servers.py`:

```python
# ABOUTME: TestClient coverage for /mcp-servers: list + display-only connected pref.
# ABOUTME: group_mcp_tools is monkeypatched to supply tool_count without a real server.

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.mcp_servers as mcp_mod
from autobots_devtools_shared_lib.dynagent.api.resources.mcp_servers import (
    build_mcp_servers_router,
    server_abbr,
)


class FakePrefs:
    def __init__(self) -> None:
        self.kv: dict[tuple[str, str, str], bool] = {}

    async def get(self, user_id, namespace):
        return {k[2]: v for k, v in self.kv.items() if k[0] == user_id and k[1] == namespace}

    async def set(self, user_id, namespace, key, value):
        self.kv[(user_id, namespace, key)] = value


@pytest.mark.parametrize(
    "name,expected", [("github", "GI"), ("jira-cloud", "JC"), ("x", "X")]
)
def test_server_abbr(name, expected):
    assert server_abbr(name) == expected


@pytest.fixture
def prefs():
    return FakePrefs()


@pytest.fixture
def client(monkeypatch, prefs):
    def fake_group(_meta):
        return [{"server": "github", "tools": [{"name": "a"}, {"name": "b"}]}], []

    monkeypatch.setattr(mcp_mod, "group_mcp_tools", fake_group)
    app = FastAPI()
    app.include_router(
        build_mcp_servers_router(
            meta=SimpleNamespace(mcp_servers_config={"github": {}}),
            prefs_store=prefs,
            user_id_dependency=lambda: "u1",
        )
    )
    return TestClient(app)


def test_list_servers_reports_tool_count(client):
    body = client.get("/mcp-servers").json()
    gh = body["servers"][0]
    assert gh["name"] == "github"
    assert gh["abbr"] == "GI"
    assert gh["tool_count"] == 2
    assert gh["connected"] is False  # default when no pref set


def test_connected_pref_reflected(client, prefs):
    prefs.kv[("u1", "mcp", "github")] = True
    assert client.get("/mcp-servers").json()["servers"][0]["connected"] is True


def test_patch_sets_connected_pref(client, prefs):
    resp = client.patch("/mcp-servers/github", json={"connected": True})
    assert resp.status_code == 200
    assert prefs.kv[("u1", "mcp", "github")] is True


def test_empty_config_returns_empty(monkeypatch, prefs):
    monkeypatch.setattr(mcp_mod, "group_mcp_tools", lambda _m: ([], []))
    app = FastAPI()
    app.include_router(
        build_mcp_servers_router(
            meta=SimpleNamespace(mcp_servers_config={}),
            prefs_store=prefs,
            user_id_dependency=lambda: "u1",
        )
    )
    assert TestClient(app).get("/mcp-servers").json() == {"servers": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_resource_mcp_servers.py -v`
Expected: FAIL — `ModuleNotFoundError: ...api.resources.mcp_servers`

- [ ] **Step 3: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/api/resources/mcp_servers.py`:

```python
# ABOUTME: /mcp-servers router — lists configured servers with a display-only connected pref.
# ABOUTME: Real OAuth connect is deferred; PATCH flips only the display flag (no handshake).

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from autobots_devtools_shared_lib.dynagent.api.resources.tools import group_mcp_tools
from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore

_NAMESPACE = "mcp"


def server_abbr(name: str) -> str:
    """Uppercase 2-char abbreviation: first letters of the first two word-parts, else first two chars."""
    parts = [p for p in re.split(r"[-_ ]+", name) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


class _ConnectedBody(BaseModel):
    connected: bool


def build_mcp_servers_router(
    meta: Any,
    prefs_store: PrefsStore,
    user_id_dependency: Any,
) -> APIRouter:
    """Build the /mcp-servers router (list + display-only connected pref)."""
    router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])

    @router.get("")
    async def list_servers(user_id: str = Depends(user_id_dependency)) -> dict[str, Any]:
        grouped, _warnings = group_mcp_tools(meta)
        counts = {g["server"]: len(g["tools"]) for g in grouped}
        prefs = await prefs_store.get(user_id, _NAMESPACE)
        servers = [
            {
                "name": name,
                "abbr": server_abbr(name),
                "connected": prefs.get(name, False),
                "tool_count": counts.get(name, 0),
            }
            for name in meta.mcp_servers_config
        ]
        return {"servers": servers}

    @router.patch("/{name}")
    async def set_connected(
        name: str, body: _ConnectedBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await prefs_store.set(user_id, _NAMESPACE, name, body.connected)
        return {"ok": True}

    return router
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_resource_mcp_servers.py -v`
Expected: PASS (7 tests — 3 parametrized + 4)

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/resources/mcp_servers.py \
        tests/unit/test_resource_mcp_servers.py
git commit -m "feat(dynagent-api): /mcp-servers router with display-only connected pref"
```

---

## Task 7: Resource router composition

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/api/router.py`
- Test: `tests/unit/test_resource_router.py`

**Interfaces:**
- Consumes: all four router builders (Tasks 2, 4, 5, 6), `register_exception_handlers` (stub from Task 2).
- Produces:
  - `def build_resource_router(*, meta, thread_store, prefs_store, backend, user_id_dependency, checkpoint_deleter=None) -> APIRouter` — one router mounting `/threads`, `/skills`, `/tools`, `/mcp-servers`.
  - `register_exception_handlers(app)` (already present; unchanged).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_resource_router.py`:

```python
# ABOUTME: Composition test: build_resource_router mounts all four resource routes.
# ABOUTME: Uses dict-backed fakes + monkeypatched discovery; asserts routes + error mapping.

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.skills as skills_mod
import autobots_devtools_shared_lib.dynagent.api.resources.tools as tools_mod
from autobots_devtools_shared_lib.dynagent.api.router import (
    build_resource_router,
    register_exception_handlers,
)


class FakeThreadStore:
    def __init__(self):
        self.rows = {}

    async def list(self, user_id, q=None):
        return []

    async def create(self, user_id, title="New chat"):
        rec = {"id": "t1", "user_id": user_id, "title": title, "created_at": None, "updated_at": None}
        self.rows["t1"] = rec
        return rec

    async def get(self, thread_id):
        return self.rows.get(thread_id)

    async def rename(self, thread_id, title):
        self.rows[thread_id]["title"] = title

    async def delete(self, thread_id):
        self.rows.pop(thread_id, None)

    async def touch(self, thread_id):
        pass


class FakePrefs:
    async def get(self, user_id, namespace):
        return {}

    async def set(self, user_id, namespace, key, value):
        pass


@pytest.fixture
def client(monkeypatch):
    async def fake_discover(_meta, _backend):
        return [], []

    monkeypatch.setattr(skills_mod, "discover_skills", fake_discover)
    monkeypatch.setattr(tools_mod, "load_mcp_tools", lambda names, cfg: [])

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        build_resource_router(
            meta=SimpleNamespace(skills_map={}, mcp_servers_config={}),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
        )
    )
    return TestClient(app)


def test_all_resource_routes_mounted(client):
    assert client.get("/threads").status_code == 200
    assert client.get("/skills").status_code == 200
    assert client.get("/tools").status_code == 200
    assert client.get("/mcp-servers").status_code == 200


def test_unknown_thread_maps_to_404(client):
    assert client.patch("/threads/nope", json={"title": "x"}).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_resource_router.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_resource_router'`

- [ ] **Step 3: Extend `router.py` with the composer**

Add to `src/autobots_devtools_shared_lib/dynagent/api/router.py` (keep the existing `register_exception_handlers`; add imports at top and the new function):

```python
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter

from autobots_devtools_shared_lib.dynagent.api.resources.mcp_servers import (
    build_mcp_servers_router,
)
from autobots_devtools_shared_lib.dynagent.api.resources.skills import build_skills_router
from autobots_devtools_shared_lib.dynagent.api.resources.threads import build_threads_router
from autobots_devtools_shared_lib.dynagent.api.resources.tools import build_tools_router
from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore, ThreadStore


def build_resource_router(
    *,
    meta: Any,
    thread_store: ThreadStore,
    prefs_store: PrefsStore,
    backend: Any,
    user_id_dependency: Callable[..., Any],
    checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None,
) -> APIRouter:
    """Compose the four resource routers into one client-agnostic APIRouter."""
    router = APIRouter()
    router.include_router(
        build_threads_router(thread_store, user_id_dependency, checkpoint_deleter)
    )
    router.include_router(
        build_skills_router(meta, backend, prefs_store, user_id_dependency)
    )
    router.include_router(build_tools_router(meta))
    router.include_router(
        build_mcp_servers_router(meta, prefs_store, user_id_dependency)
    )
    return router
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_resource_router.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the whole resource plane + lint/type-check**

Run:
```bash
.venv/bin/pytest tests/unit/test_thread_store_protocols.py tests/unit/test_resource_threads.py \
  tests/unit/test_skills_discovery.py tests/unit/test_resource_skills.py \
  tests/unit/test_resource_tools.py tests/unit/test_resource_mcp_servers.py \
  tests/unit/test_resource_router.py -q
make lint && make type-check
```
Expected: all resource-plane tests PASS; ruff clean; pyright clean on `dynagent/api/`.

- [ ] **Step 6: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/api/router.py \
        tests/unit/test_resource_router.py
git commit -m "feat(dynagent-api): build_resource_router composes the four resource routers"
```

---

## Task 8: Rail stream — best-effort guard + touch-on-finish hook

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/ui/rail_stream.py`
- Test: `tests/unit/test_rail_stream_touch.py`

**Interfaces:**
- Consumes: existing `ActivityProjection`.
- Produces (changed signatures):
  - `async def project_stream(inner, mcp_servers, main_agent_name=None, on_run_finished=None)` — `on_run_finished: Callable[[str], Awaitable[None]] | None`; called best-effort with `thread_id` when a `RUN_FINISHED` event carries one. Projection `observe`/`snapshot` wrapped so a projection error drops the delta but passes the event through.
  - `RailAGUIAgent.__init__(..., on_run_finished=None)` stored and threaded into `project_stream`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_rail_stream_touch.py`:

```python
# ABOUTME: Tests project_stream's touch-on-finish hook and best-effort projection guard.
# ABOUTME: A raising projection must not break passthrough; RUN_FINISHED triggers touch.

from unittest.mock import patch

import pytest


async def _aiter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_calls_on_run_finished_with_thread_id():
    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import project_stream

    touched: list[str] = []

    async def on_finish(thread_id: str) -> None:
        touched.append(thread_id)

    events = [
        {"type": "RUN_STARTED", "thread_id": "abc", "_t_ms": 0},
        {"type": "RUN_FINISHED", "thread_id": "abc", "_t_ms": 5},
    ]
    out = [ev async for ev in project_stream(_aiter(events), set(), on_run_finished=on_finish)]

    passthrough = [ev for ev in out if isinstance(ev, dict)]
    assert passthrough == events
    assert touched == ["abc"]


@pytest.mark.asyncio
async def test_projection_error_drops_delta_not_stream():
    from autobots_devtools_shared_lib.dynagent.ui import rail_stream

    events = [{"type": "RUN_STARTED", "thread_id": "z", "_t_ms": 0}]

    with patch.object(
        rail_stream.ActivityProjection, "observe", side_effect=RuntimeError("boom")
    ):
        out = [ev async for ev in rail_stream.project_stream(_aiter(events), set())]

    # the token/event stream survives even though projection blew up
    assert [ev for ev in out if isinstance(ev, dict)] == events
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_rail_stream_touch.py -v`
Expected: FAIL — `TypeError: project_stream() got an unexpected keyword argument 'on_run_finished'`

- [ ] **Step 3: Update `rail_stream.py`**

Replace the body of `project_stream` and `RailAGUIAgent` in `src/autobots_devtools_shared_lib/dynagent/ui/rail_stream.py`. New full file:

```python
# ABOUTME: Streams the derived AMA activity rail alongside the AG-UI event stream.
# ABOUTME: Wraps LangGraphAGUIAgent.run, injecting non-destructive STATE_DELTA updates.

import time
from collections.abc import AsyncIterator, Awaitable, Callable

from ag_ui.core import EventType, StateDeltaEvent
from copilotkit import LangGraphAGUIAgent

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.ui.activity_projection import ActivityProjection

logger = get_logger(__name__)


def _to_dict(event) -> dict:
    if isinstance(event, dict):
        return event
    return event.model_dump()


async def project_stream(
    inner: AsyncIterator,
    mcp_servers: set[str],
    main_agent_name: str | None = None,
    on_run_finished: Callable[[str], Awaitable[None]] | None = None,
) -> AsyncIterator:
    """Yield every event from `inner`; after each rail change, inject a STATE_DELTA.

    The delta is JSON Patch `add /activity` + `add /stats` — non-destructive, so it never
    clobbers the raw deepagents state keys (files/todos) already carried by STATE_SNAPSHOT.

    Projection is best-effort: any failure inside observe/snapshot drops the rail delta but
    never interrupts the underlying token stream. When `on_run_finished` is supplied it is
    invoked (best-effort) with the run's thread_id on RUN_FINISHED — the sole write-back
    from the streaming plane into the ThreadStore (touch()).
    """
    proj = ActivityProjection(mcp_servers, main_agent_name)
    t0: float | None = None
    async for event in inner:
        data = _to_dict(event)
        now = time.monotonic() * 1000
        if t0 is None:
            t0 = now
        data.setdefault("_t_ms", int(now - t0))
        try:
            proj.observe(data)
        except Exception:
            logger.warning("activity projection observe failed; dropping delta", exc_info=True)
            proj.dirty = False
        yield event
        if data.get("type") == "RUN_FINISHED" and on_run_finished is not None:
            thread_id = data.get("thread_id")
            if thread_id:
                try:
                    await on_run_finished(thread_id)
                except Exception:
                    logger.warning("on_run_finished(touch) failed", exc_info=True)
        if proj.dirty:
            proj.dirty = False
            try:
                snap = proj.snapshot()
            except Exception:
                logger.warning("activity projection snapshot failed; dropping delta", exc_info=True)
                continue
            yield StateDeltaEvent(
                type=EventType.STATE_DELTA,
                delta=[
                    {"op": "add", "path": "/activity", "value": snap["activity"]},
                    {"op": "add", "path": "/stats", "value": snap["stats"]},
                ],
            )


class RailAGUIAgent(LangGraphAGUIAgent):
    """LangGraphAGUIAgent that streams the derived activity rail via STATE_DELTA."""

    def __init__(
        self,
        *args,
        mcp_servers: set[str] | None = None,
        main_agent_name: str | None = None,
        on_run_finished: Callable[[str], Awaitable[None]] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._mcp_servers = mcp_servers or set()
        self._main_agent_name = main_agent_name
        self._on_run_finished = on_run_finished

    async def run(self, input):  # matches LangGraphAGUIAgent's base signature (self, input)
        async for event in project_stream(
            super().run(input),
            self._mcp_servers,
            self._main_agent_name,
            self._on_run_finished,
        ):
            yield event
```

- [ ] **Step 4: Run tests to verify pass (new + existing rail tests)**

Run: `.venv/bin/pytest tests/unit/test_rail_stream_touch.py tests/unit/test_rail_stream.py -v`
Expected: PASS (all — the existing `test_rail_stream.py` still passes; `on_run_finished` defaults to `None`).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/ui/rail_stream.py \
        tests/unit/test_rail_stream_touch.py
git commit -m "feat(dynagent-ui): best-effort rail projection + touch-on-finish hook"
```

---

## Task 9: AG-UI endpoint mount helper

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/agui_endpoint.py`
- Test: `tests/unit/test_agui_endpoint.py`

**Interfaces:**
- Consumes: `RailAGUIAgent` (Task 8), lazy `ag_ui_langgraph.add_langgraph_fastapi_endpoint`.
- Produces:
  - `def mount_agui_endpoint(app, graph, *, graph_id, mcp_servers, main_agent_name=None, path="/agent", on_run_finished=None) -> None` — builds a `RailAGUIAgent` and mounts it via `add_langgraph_fastapi_endpoint`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agui_endpoint.py`:

```python
# ABOUTME: Smoke test for mount_agui_endpoint — mounts a RailAGUIAgent at the given path.
# ABOUTME: Uses a mock graph; asserts the route registers and RailAGUIAgent gets rail kwargs.

from unittest.mock import MagicMock

import pytest

pytest.importorskip("copilotkit")

_MODULE = "autobots_devtools_shared_lib.dynagent.ui.agui_endpoint"


def test_mounts_route_and_builds_rail_agent():
    from unittest.mock import patch

    from fastapi import FastAPI

    from autobots_devtools_shared_lib.dynagent.ui.agui_endpoint import mount_agui_endpoint
    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import RailAGUIAgent

    app = FastAPI()
    graph = MagicMock(name="graph")

    with patch(f"{_MODULE}.RailAGUIAgent", wraps=RailAGUIAgent) as spy:
        mount_agui_endpoint(
            app,
            graph,
            graph_id="assistant",
            mcp_servers={"github"},
            main_agent_name="assistant",
            path="/agent",
        )

    assert "/agent" in {route.path for route in app.routes}
    assert spy.call_args.kwargs["mcp_servers"] == {"github"}
    assert spy.call_args.kwargs["main_agent_name"] == "assistant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_agui_endpoint.py -v`
Expected: FAIL — `ModuleNotFoundError: ...ui.agui_endpoint`

- [ ] **Step 3: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/ui/agui_endpoint.py`:

```python
# ABOUTME: Mounts the CopilotKit AG-UI streaming endpoint (RailAGUIAgent) on a FastAPI app.
# ABOUTME: AG-UI-specific; lazily imports ag_ui_langgraph so non-UI paths never need it.

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.ui.rail_stream import RailAGUIAgent

logger = get_logger(__name__)


def mount_agui_endpoint(
    app: FastAPI,
    graph: Any,
    *,
    graph_id: str,
    mcp_servers: set[str],
    main_agent_name: str | None = None,
    path: str = "/agent",
    on_run_finished: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    """Wrap `graph` in a RailAGUIAgent and mount it over the AG-UI protocol at `path`."""
    from ag_ui_langgraph import add_langgraph_fastapi_endpoint

    agent = RailAGUIAgent(
        name=graph_id,
        description="Dynagent deep-agent coordinator served over AG-UI.",
        graph=graph,
        mcp_servers=mcp_servers,
        main_agent_name=main_agent_name,
        on_run_finished=on_run_finished,
    )
    add_langgraph_fastapi_endpoint(app, agent, path)
    logger.info("Mounted AG-UI deep agent graphId='%s' at '%s'", graph_id, path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_agui_endpoint.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/ui/agui_endpoint.py \
        tests/unit/test_agui_endpoint.py
git commit -m "feat(dynagent-ui): mount_agui_endpoint helper for the AG-UI streaming plane"
```

---

## Task 10: `create_agui_app` — compose both planes; delete the spike

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/agui_app.py`
- Delete: `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`
- Delete: `tests/unit/test_copilotkit_server.py`
- Test: `tests/unit/test_agui_app.py`

**Interfaces:**
- Consumes: `create_base_deepagent` (default `agent_factory`), `collapse_system_messages`, `AgentMeta`, `get_default_agent`, `get_langfuse_handler`, `mount_agui_endpoint` (Task 9), `build_resource_router` + `register_exception_handlers` (Task 7).
- Produces:
  - `def create_agui_app(*, checkpointer, thread_store, prefs_store, backend, user_id_dependency, agent_name=None, checkpoint_deleter=None, agent_factory=create_base_deepagent, cors_origins=None, path="/agent") -> FastAPI`.
  - App mounts: `/agent` (AG-UI), `/threads`, `/skills`, `/tools`, `/mcp-servers`, `/health`; CORS configured; domain-error handlers registered; `on_run_finished` wired to `thread_store.touch`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agui_app.py`:

```python
# ABOUTME: Composition smoke test for create_agui_app using a stub agent factory (no LLM).
# ABOUTME: Asserts /agent + all resource routes + /health mount and CORS is configured.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("copilotkit")

_MODULE = "autobots_devtools_shared_lib.dynagent.ui.agui_app"


class FakeThreadStore:
    async def list(self, user_id, q=None):
        return []

    async def create(self, user_id, title="New chat"):
        return {"id": "t1", "user_id": user_id, "title": title, "created_at": None, "updated_at": None}

    async def get(self, thread_id):
        return None

    async def rename(self, thread_id, title):
        pass

    async def delete(self, thread_id):
        pass

    async def touch(self, thread_id):
        pass


class FakePrefs:
    async def get(self, user_id, namespace):
        return {}

    async def set(self, user_id, namespace, key, value):
        pass


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
def test_mounts_both_planes_and_health(_mock_lf):
    from autobots_devtools_shared_lib.dynagent.ui.agui_app import create_agui_app

    fake_meta = SimpleNamespace(skills_map={}, mcp_servers_config={})
    stub_graph = MagicMock(name="graph")
    stub_graph.with_config.return_value = stub_graph

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.agent_meta.AgentMeta.instance",
        return_value=fake_meta,
    ):
        app = create_agui_app(
            checkpointer=MagicMock(),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
            agent_name="assistant",
            agent_factory=lambda **kwargs: stub_graph,
        )

    paths = {route.path for route in app.routes}
    assert "/agent" in paths
    assert "/threads" in paths
    assert "/skills" in paths
    assert "/tools" in paths
    assert "/mcp-servers" in paths
    assert "/health" in paths


@patch(f"{_MODULE}.get_langfuse_handler", return_value=None)
def test_agent_factory_receives_copilotkit_and_collapse_middleware(_mock_lf):
    from autobots_devtools_shared_lib.dynagent.ui import agui_app

    fake_meta = SimpleNamespace(skills_map={}, mcp_servers_config={})
    captured = {}

    def stub_factory(**kwargs):
        captured.update(kwargs)
        g = MagicMock()
        g.with_config.return_value = g
        return g

    with patch(
        "autobots_devtools_shared_lib.dynagent.agents.agent_meta.AgentMeta.instance",
        return_value=fake_meta,
    ):
        agui_app.create_agui_app(
            checkpointer=MagicMock(),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
            agent_name="assistant",
            agent_factory=stub_factory,
        )

    mw = captured["middleware"]
    assert type(mw[0]).__name__ == "CopilotKitMiddleware"
    assert mw[-1] is agui_app.collapse_system_messages
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_agui_app.py -v`
Expected: FAIL — `ModuleNotFoundError: ...ui.agui_app`

- [ ] **Step 3: Write the implementation**

Create `src/autobots_devtools_shared_lib/dynagent/ui/agui_app.py`:

```python
# ABOUTME: create_agui_app composes the AG-UI streaming plane with the REST resource plane.
# ABOUTME: One create_base_deepagent graph + one checkpointer serve /agent and /threads,/skills,...

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_handler
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.base_deepagent import create_base_deepagent
from autobots_devtools_shared_lib.dynagent.api.router import (
    build_resource_router,
    register_exception_handlers,
)
from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore, ThreadStore
from autobots_devtools_shared_lib.dynagent.ui.agui_endpoint import mount_agui_endpoint
from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
    collapse_system_messages,
)

logger = get_logger(__name__)

_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]


def _resolve_origins(cors_origins: list[str] | None) -> list[str]:
    if cors_origins is not None:
        return cors_origins
    raw = os.getenv("ATLAS_UI_ORIGINS", ",".join(_DEFAULT_ORIGINS))
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_agui_app(
    *,
    checkpointer: Any,
    thread_store: ThreadStore,
    prefs_store: PrefsStore,
    backend: Any,
    user_id_dependency: Callable[..., Any],
    agent_name: str | None = None,
    checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None,
    agent_factory: Callable[..., Any] = create_base_deepagent,
    cors_origins: list[str] | None = None,
    path: str = "/agent",
) -> FastAPI:
    """Build the FastAPI app serving the AG-UI stream + client-agnostic resource routers.

    Both planes share one deep-agent graph and one checkpointer. Injected stores replace
    the spike's module-level InMemorySaver; CORS origins and identity are configuration.
    """
    from copilotkit import CopilotKitMiddleware

    meta = AgentMeta.instance()
    graph_id = agent_name or get_default_agent() or "dynagent"

    graph = agent_factory(
        checkpointer=checkpointer,
        initial_agent_name=agent_name,
        middleware=[CopilotKitMiddleware(), collapse_system_messages],
    )
    langfuse_handler = get_langfuse_handler()
    config: dict[str, Any] = {"recursion_limit": 50}
    if langfuse_handler is not None:
        config["callbacks"] = [langfuse_handler]
    graph = graph.with_config(config)

    origins = _resolve_origins(cors_origins)
    app = FastAPI(title=f"Dynagent AG-UI ({graph_id})")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(
        build_resource_router(
            meta=meta,
            thread_store=thread_store,
            prefs_store=prefs_store,
            backend=backend,
            user_id_dependency=user_id_dependency,
            checkpoint_deleter=checkpoint_deleter,
        )
    )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "graph": graph_id}

    mount_agui_endpoint(
        app,
        graph,
        graph_id=graph_id,
        mcp_servers=set(meta.mcp_servers_config.keys()),
        main_agent_name=agent_name or get_default_agent(),
        path=path,
        on_run_finished=thread_store.touch,
    )
    logger.info("create_agui_app ready · graphId='%s' · CORS origins=%s", graph_id, origins)
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_agui_app.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Delete the spike + its test**

```bash
git rm src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py \
       tests/unit/test_copilotkit_server.py
```

- [ ] **Step 6: Verify nothing else imports the deleted spike**

Run: `grep -rn "copilotkit_server\|create_copilotkit_app" src/ tests/ ../autobots-agents-mer/src ../autobots-agents-mer/sbin 2>/dev/null`
Expected: no matches. If any appear, update them to `create_agui_app`/`mount_agui_endpoint` before continuing.

- [ ] **Step 7: Run the full UI-plane test set + lint/type-check**

Run:
```bash
.venv/bin/pytest tests/unit/test_rail_stream.py tests/unit/test_rail_stream_touch.py \
  tests/unit/test_agui_endpoint.py tests/unit/test_agui_app.py -q
make lint && make type-check
```
Expected: PASS; ruff clean; pyright clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(dynagent-ui): create_agui_app composes streaming + resource planes; drop spike"
```

---

## Task 11: mer — AMA Postgres models

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/common/db/models_ama.py`
- Modify: `autobots-agents-mer/src/autobots_agents_mer/common/db/engine.py`
- Test: `autobots-agents-mer/tests/unit/domains/test_ama_models.py`

> All commands in Tasks 11–14 run from the mer repo: `cd ../autobots-agents-mer` (relative to shared-lib). The shared venv is still `../.venv`.

**Interfaces:**
- Produces:
  - `class AmaThreadEntity(SQLModel, table=True)` — table `ama_threads`, columns `id` (PK), `user_id` (indexed), `title`, `created_at`, `updated_at` (server_default now, onupdate now).
  - `class AmaUserPrefEntity(SQLModel, table=True)` — table `ama_user_prefs`, composite PK `(user_id, namespace, key)`, column `value: bool`.
  - `engine.py` imports both so `SQLModel.metadata.create_all` registers them (idempotent — this repo has no Alembic; create_all is the migration).

- [ ] **Step 1: Write the failing test**

Create `autobots-agents-mer/tests/unit/domains/test_ama_models.py`:

```python
# ABOUTME: Unit tests for the AMA SQLModel tables — column/PK shape via create_all on SQLite.
# ABOUTME: No Postgres needed; asserts tables register and round-trip through a sync session.

from sqlalchemy import create_engine, inspect
from sqlmodel import Session, SQLModel


def test_tables_register_and_columns_present():
    from autobots_agents_mer.common.db.models_ama import AmaThreadEntity, AmaUserPrefEntity  # noqa: F401

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"ama_threads", "ama_user_prefs"} <= tables

    cols = {c["name"] for c in inspect(engine).get_columns("ama_threads")}
    assert {"id", "user_id", "title", "created_at", "updated_at"} <= cols


def test_thread_row_roundtrips():
    from autobots_agents_mer.common.db.models_ama import AmaThreadEntity

    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(AmaThreadEntity(id="t1", user_id="u1", title="Hello"))
        session.commit()
        fetched = session.get(AmaThreadEntity, "t1")
        assert fetched is not None
        assert fetched.user_id == "u1"
        assert fetched.created_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/pytest tests/unit/domains/test_ama_models.py -v`
Expected: FAIL — `ModuleNotFoundError: ...common.db.models_ama`

- [ ] **Step 3: Write the models**

Create `autobots-agents-mer/src/autobots_agents_mer/common/db/models_ama.py`:

```python
# ABOUTME: SQLModel tables for the AMA UI backend — thread index + per-user UI prefs.
# ABOUTME: ama_threads holds metadata only (content lives in the LangGraph checkpointer).

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class AmaThreadEntity(SQLModel, table=True):
    """Left-rail conversation metadata. Never stores message content."""

    __tablename__ = "ama_threads"  # pyright: ignore[reportAssignmentType]

    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    title: str = Field(default="New chat")
    created_at: datetime = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=lambda: datetime.now(UTC),
            nullable=False,
        ),
    )


class AmaUserPrefEntity(SQLModel, table=True):
    """Narrow per-user KV for display-only UI prefs (namespace = 'skills' | 'mcp')."""

    __tablename__ = "ama_user_prefs"  # pyright: ignore[reportAssignmentType]

    user_id: str = Field(primary_key=True)
    namespace: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    value: bool = Field(default=True)
```

- [ ] **Step 4: Register the models in `engine.py`**

Add these imports alongside the existing model imports near the top of `autobots-agents-mer/src/autobots_agents_mer/common/db/engine.py`:

```python
from autobots_agents_mer.common.db.models_ama import (  # noqa: F401
    AmaThreadEntity,
    AmaUserPrefEntity,
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `../.venv/bin/pytest tests/unit/domains/test_ama_models.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit (from inside mer)**

```bash
git add src/autobots_agents_mer/common/db/models_ama.py \
        src/autobots_agents_mer/common/db/engine.py \
        tests/unit/domains/test_ama_models.py
git commit -m "feat(ama-web): ama_threads + ama_user_prefs SQLModel tables"
```

---

## Task 12: mer — Postgres ThreadStore + PrefsStore

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/__init__.py`
- Create: `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/thread_store_pg.py`
- Test: `autobots-agents-mer/tests/integration/domains/ama/__init__.py`, `autobots-agents-mer/tests/integration/domains/ama/test_thread_store_pg.py`

**Interfaces:**
- Consumes: `AmaThreadEntity`, `AmaUserPrefEntity` (Task 11), `sessionmaker[Session]`, and the shared-lib `ThreadRecord` shape.
- Produces:
  - `class PgThreadStore` implementing `ThreadStore` (async methods wrap sync SQLAlchemy via `asyncio.to_thread`). `create` mints a UUID `id`. `list` filters by `user_id`, optional case-insensitive title `q`, ordered by `updated_at` desc.
  - `class PgPrefsStore` implementing `PrefsStore` (upsert into `ama_user_prefs`).

> Integration note: the store is DSN-agnostic (it only holds a `sessionmaker`). Tests drive it against an in-process **SQLite** engine so they run in CI without a Postgres sidecar; Postgres is the production target via `MER_DATABASE_URL`. Marked `integration` per the spec.

- [ ] **Step 1: Create the package markers**

Create `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/__init__.py`:

```python
# ABOUTME: Concrete AMA web app — Postgres stores + identity wiring create_agui_app.
# ABOUTME: Runs in parallel with the Chainlit AMA server (different process/port).
```

Create `autobots-agents-mer/tests/integration/domains/ama/__init__.py` (empty file).

- [ ] **Step 2: Write the failing test**

Create `autobots-agents-mer/tests/integration/domains/ama/test_thread_store_pg.py`:

```python
# ABOUTME: Integration tests for PgThreadStore/PgPrefsStore against an in-process SQLite engine.
# ABOUTME: Exercises CRUD, user scoping, title filter, ordering, and prefs upsert.

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

pytestmark = pytest.mark.integration


@pytest.fixture
def session_factory():
    from autobots_agents_mer.common.db.models_ama import (  # noqa: F401
        AmaThreadEntity,
        AmaUserPrefEntity,
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


async def test_create_list_scoped_by_user(session_factory):
    from autobots_agents_mer.domains.ama.web.thread_store_pg import PgThreadStore

    store = PgThreadStore(session_factory)
    a = await store.create("u1", "Alpha")
    await store.create("u2", "Beta")

    listed = await store.list("u1")
    assert [r["id"] for r in listed] == [a["id"]]
    assert listed[0]["title"] == "Alpha"


async def test_rename_and_get(session_factory):
    from autobots_agents_mer.domains.ama.web.thread_store_pg import PgThreadStore

    store = PgThreadStore(session_factory)
    rec = await store.create("u1")
    await store.rename(rec["id"], "Renamed")
    got = await store.get(rec["id"])
    assert got is not None
    assert got["title"] == "Renamed"


async def test_title_filter(session_factory):
    from autobots_agents_mer.domains.ama.web.thread_store_pg import PgThreadStore

    store = PgThreadStore(session_factory)
    await store.create("u1", "Shopping list")
    await store.create("u1", "Work notes")
    listed = await store.list("u1", q="shop")
    assert [r["title"] for r in listed] == ["Shopping list"]


async def test_delete_removes_row(session_factory):
    from autobots_agents_mer.domains.ama.web.thread_store_pg import PgThreadStore

    store = PgThreadStore(session_factory)
    rec = await store.create("u1")
    await store.delete(rec["id"])
    assert await store.get(rec["id"]) is None


async def test_prefs_upsert_and_get(session_factory):
    from autobots_agents_mer.domains.ama.web.thread_store_pg import PgPrefsStore

    prefs = PgPrefsStore(session_factory)
    await prefs.set("u1", "skills", "demo-fact", False)
    await prefs.set("u1", "skills", "demo-fact", True)  # upsert
    await prefs.set("u1", "mcp", "github", True)

    assert await prefs.get("u1", "skills") == {"demo-fact": True}
    assert await prefs.get("u1", "mcp") == {"github": True}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `../.venv/bin/pytest tests/integration/domains/ama/test_thread_store_pg.py -v`
Expected: FAIL — `ModuleNotFoundError: ...domains.ama.web.thread_store_pg`

- [ ] **Step 4: Write the implementation**

Create `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/thread_store_pg.py`:

```python
# ABOUTME: Postgres-backed ThreadStore/PrefsStore for the AMA UI backend (SQLAlchemy).
# ABOUTME: Async methods offload the sync ORM to a thread; DSN-agnostic (any sessionmaker).

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from autobots_devtools_shared_lib.dynagent.api.thread_store import ThreadRecord

from autobots_agents_mer.common.db.models_ama import AmaThreadEntity, AmaUserPrefEntity

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _to_record(entity: AmaThreadEntity) -> ThreadRecord:
    return {
        "id": entity.id,
        "user_id": entity.user_id,
        "title": entity.title,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }


class PgThreadStore:
    """ThreadStore over SQLAlchemy. Each method uses a short-lived session."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    async def list(self, user_id: str, q: str | None = None) -> list[ThreadRecord]:
        return await asyncio.to_thread(self._list_sync, user_id, q)

    def _list_sync(self, user_id: str, q: str | None) -> list[ThreadRecord]:
        with self._session_factory() as session:
            query = session.query(AmaThreadEntity).filter(AmaThreadEntity.user_id == user_id)
            if q:
                query = query.filter(AmaThreadEntity.title.ilike(f"%{q}%"))
            rows = query.order_by(AmaThreadEntity.updated_at.desc()).all()
            return [_to_record(r) for r in rows]

    async def create(self, user_id: str, title: str = "New chat") -> ThreadRecord:
        return await asyncio.to_thread(self._create_sync, user_id, title)

    def _create_sync(self, user_id: str, title: str) -> ThreadRecord:
        with self._session_factory() as session:
            try:
                entity = AmaThreadEntity(id=str(uuid.uuid4()), user_id=user_id, title=title)
                session.add(entity)
                session.commit()
                session.refresh(entity)
                return _to_record(entity)
            except Exception:
                session.rollback()
                raise

    async def get(self, thread_id: str) -> ThreadRecord | None:
        return await asyncio.to_thread(self._get_sync, thread_id)

    def _get_sync(self, thread_id: str) -> ThreadRecord | None:
        with self._session_factory() as session:
            entity = session.get(AmaThreadEntity, thread_id)
            return _to_record(entity) if entity is not None else None

    async def rename(self, thread_id: str, title: str) -> None:
        await asyncio.to_thread(self._rename_sync, thread_id, title)

    def _rename_sync(self, thread_id: str, title: str) -> None:
        with self._session_factory() as session:
            try:
                entity = session.get(AmaThreadEntity, thread_id)
                if entity is not None:
                    entity.title = title
                    session.commit()
            except Exception:
                session.rollback()
                raise

    async def delete(self, thread_id: str) -> None:
        await asyncio.to_thread(self._delete_sync, thread_id)

    def _delete_sync(self, thread_id: str) -> None:
        with self._session_factory() as session:
            try:
                entity = session.get(AmaThreadEntity, thread_id)
                if entity is not None:
                    session.delete(entity)
                    session.commit()
            except Exception:
                session.rollback()
                raise

    async def touch(self, thread_id: str) -> None:
        await asyncio.to_thread(self._touch_sync, thread_id)

    def _touch_sync(self, thread_id: str) -> None:
        from datetime import UTC, datetime

        with self._session_factory() as session:
            try:
                entity = session.get(AmaThreadEntity, thread_id)
                if entity is not None:
                    entity.updated_at = datetime.now(UTC)
                    session.commit()
            except Exception:
                session.rollback()
                raise


class PgPrefsStore:
    """PrefsStore over SQLAlchemy — upserts into the composite-key ama_user_prefs table."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    async def get(self, user_id: str, namespace: str) -> dict[str, bool]:
        return await asyncio.to_thread(self._get_sync, user_id, namespace)

    def _get_sync(self, user_id: str, namespace: str) -> dict[str, bool]:
        with self._session_factory() as session:
            rows = (
                session.query(AmaUserPrefEntity)
                .filter(
                    AmaUserPrefEntity.user_id == user_id,
                    AmaUserPrefEntity.namespace == namespace,
                )
                .all()
            )
            return {r.key: r.value for r in rows}

    async def set(self, user_id: str, namespace: str, key: str, value: bool) -> None:
        await asyncio.to_thread(self._set_sync, user_id, namespace, key, value)

    def _set_sync(self, user_id: str, namespace: str, key: str, value: bool) -> None:
        with self._session_factory() as session:
            try:
                entity = session.get(AmaUserPrefEntity, (user_id, namespace, key))
                if entity is None:
                    session.add(
                        AmaUserPrefEntity(
                            user_id=user_id, namespace=namespace, key=key, value=value
                        )
                    )
                else:
                    entity.value = value
                session.commit()
            except Exception:
                session.rollback()
                raise
```

- [ ] **Step 5: Run test to verify it passes**

Run: `../.venv/bin/pytest tests/integration/domains/ama/test_thread_store_pg.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit (from inside mer)**

```bash
git add src/autobots_agents_mer/domains/ama/web/__init__.py \
        src/autobots_agents_mer/domains/ama/web/thread_store_pg.py \
        tests/integration/domains/ama/__init__.py \
        tests/integration/domains/ama/test_thread_store_pg.py
git commit -m "feat(ama-web): Postgres ThreadStore + PrefsStore implementations"
```

---

## Task 13: mer — identity resolution + concrete app

**Files:**
- Create: `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/identity.py`
- Create: `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/app.py`
- Test: `autobots-agents-mer/tests/unit/domains/test_ama_identity.py`

**Interfaces:**
- Consumes: `create_agui_app` (Task 10), `PgThreadStore`/`PgPrefsStore` (Task 12), `get_checkpointer` (`domains/ama/memory.py`), `resolve_backend` + `AgentMeta` (shared-lib), `init_db_engine` (`common/db/engine.py`), `FileServerBackend` (shared-lib).
- Produces:
  - `def resolve_user_id(request: Request) -> str` — trusted `X-User-Id` header if present, else `DEFAULT_USER_ID` env (fallback `"local-user"`).
  - `async def build_app() -> FastAPI` — resolves stores/checkpointer/backend/identity and calls `create_agui_app(...)`; module exposes `app` (lazily built) for uvicorn.

- [ ] **Step 1: Write the failing test (identity only — pure)**

Create `autobots-agents-mer/tests/unit/domains/test_ama_identity.py`:

```python
# ABOUTME: Unit tests for resolve_user_id: trusted header wins, else DEFAULT_USER_ID env.
# ABOUTME: Pure — builds a Starlette Request stub; no app, no DB.

from starlette.requests import Request


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw})


def test_header_identity_wins(monkeypatch):
    from autobots_agents_mer.domains.ama.web.identity import resolve_user_id

    monkeypatch.setenv("DEFAULT_USER_ID", "env-user")
    assert resolve_user_id(_request({"X-User-Id": "alice"})) == "alice"


def test_falls_back_to_default_env(monkeypatch):
    from autobots_agents_mer.domains.ama.web.identity import resolve_user_id

    monkeypatch.setenv("DEFAULT_USER_ID", "env-user")
    assert resolve_user_id(_request({})) == "env-user"


def test_default_when_env_unset(monkeypatch):
    from autobots_agents_mer.domains.ama.web.identity import resolve_user_id

    monkeypatch.delenv("DEFAULT_USER_ID", raising=False)
    assert resolve_user_id(_request({})) == "local-user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/pytest tests/unit/domains/test_ama_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: ...domains.ama.web.identity`

- [ ] **Step 3: Write the identity module**

Create `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/identity.py`:

```python
# ABOUTME: Identity resolution for the AMA web app — trusted header, else dev DEFAULT_USER_ID.
# ABOUTME: GitHub OAuth is a later drop-in at this same seam (auth hardening deferred).

from __future__ import annotations

import os

from starlette.requests import Request


def resolve_user_id(request: Request) -> str:
    """Resolve the caller's user_id: trusted X-User-Id header, else DEFAULT_USER_ID env.

    The React app / CopilotKit passes the identity so AG-UI runs and REST calls share the
    same user_id (threads created in chat appear in the list). Header trust and JWT
    verification are hardened later; the seam is fixed here.
    """
    header = request.headers.get("X-User-Id")
    if header:
        return header
    return os.getenv("DEFAULT_USER_ID", "local-user")
```

- [ ] **Step 4: Run identity test to verify it passes**

Run: `../.venv/bin/pytest tests/unit/domains/test_ama_identity.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the concrete app module**

Create `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/app.py`:

```python
# ABOUTME: Concrete AMA web app — wires Postgres stores, checkpointer, backend, identity.
# ABOUTME: Runs in parallel with the Chainlit AMA server; same config, different process/port.

from __future__ import annotations

import os

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.deep_backend import resolve_backend
from autobots_devtools_shared_lib.dynagent.ui.agui_app import create_agui_app
from fastapi import FastAPI

from autobots_agents_mer.common.configs import env_config  # noqa: F401  (loads .env)
from autobots_agents_mer.common.db.engine import init_db_engine
from autobots_agents_mer.domains.ama.memory import get_checkpointer
from autobots_agents_mer.domains.ama.settings import init_ama_settings
from autobots_agents_mer.domains.ama.web.identity import resolve_user_id
from autobots_agents_mer.domains.ama.web.thread_store_pg import PgPrefsStore, PgThreadStore

logger = get_logger(__file__)


def _discovery_backend():
    """Materialize a concrete backend for skills discovery from the domain's config.

    resolve_backend may return a runtime-bound factory (e.g. fserver). For introspection
    there is no runtime, so a factory is called with a minimal stub carrying empty state.
    """
    meta = AgentMeta.instance()
    resolved = resolve_backend(meta.backend_config)
    if callable(resolved):

        class _StubRuntime:
            state: dict = {}

        return resolved(_StubRuntime())
    return resolved


async def build_app() -> FastAPI:
    """Build the AMA AG-UI FastAPI app with Postgres stores and durable checkpointer."""
    init_ama_settings()

    session_factory = init_db_engine(os.environ["MER_DATABASE_URL"])
    thread_store = PgThreadStore(session_factory)
    prefs_store = PgPrefsStore(session_factory)

    checkpointer = await get_checkpointer()

    async def checkpoint_deleter(thread_id: str) -> None:
        await checkpointer.adelete_thread(thread_id)

    return create_agui_app(
        checkpointer=checkpointer,
        thread_store=thread_store,
        prefs_store=prefs_store,
        backend=_discovery_backend(),
        user_id_dependency=resolve_user_id,
        checkpoint_deleter=checkpoint_deleter,
    )


async def _lifespan_app() -> FastAPI:
    return await build_app()
```

Note: `run_ama_web.sh` (Task 14) launches this via a tiny async bootstrap that awaits `build_app()`; the checkpointer is async so the app cannot be a bare module-level `create_agui_app(...)` call.

- [ ] **Step 6: Verify the app module imports cleanly (no DB needed for import)**

Run: `../.venv/bin/python -c "import autobots_agents_mer.domains.ama.web.app as m; print('import ok:', hasattr(m, 'build_app'))"`
Expected: `import ok: True` (importing must not touch the DB — `build_app` is only called at startup).

- [ ] **Step 7: Run mer unit + integration AMA tests + lint/type-check**

Run:
```bash
../.venv/bin/pytest tests/unit/domains/test_ama_identity.py \
  tests/unit/domains/test_ama_models.py \
  tests/integration/domains/ama/test_thread_store_pg.py -q
make lint && make type-check
```
Expected: PASS; ruff clean; pyright clean.

- [ ] **Step 8: Commit (from inside mer)**

```bash
git add src/autobots_agents_mer/domains/ama/web/identity.py \
        src/autobots_agents_mer/domains/ama/web/app.py \
        tests/unit/domains/test_ama_identity.py
git commit -m "feat(ama-web): identity resolution + concrete create_agui_app wiring"
```

---

## Task 14: mer — run script (parallel port)

**Files:**
- Create: `autobots-agents-mer/sbin/run_ama_web.sh`
- Create: `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/__main__.py`

**Interfaces:**
- Consumes: `build_app()` (Task 13).
- Produces:
  - `__main__.py` — async bootstrap that awaits `build_app()` and runs uvicorn.
  - `run_ama_web.sh` — exports the same AMA env vars as `run_ama.sh`, runs on port 8001.

- [ ] **Step 1: Write the bootstrap entry point**

Create `autobots-agents-mer/src/autobots_agents_mer/domains/ama/web/__main__.py`:

```python
# ABOUTME: uvicorn bootstrap for the AMA AG-UI web app (async build_app + serve).
# ABOUTME: Runs on its own port, in parallel with the Chainlit AMA server.

from __future__ import annotations

import asyncio
import os

import uvicorn

from autobots_agents_mer.domains.ama.web.app import build_app


async def _serve() -> None:
    app = await build_app()
    port = int(os.getenv("PORT", "8001"))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")  # noqa: S104
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    asyncio.run(_serve())
```

- [ ] **Step 2: Write the run script**

Create `autobots-agents-mer/sbin/run_ama_web.sh`:

```bash
#!/usr/bin/env bash
# ABOUTME: Run the AMA AG-UI web app (FastAPI/CopilotKit) in development mode.
# ABOUTME: Parallel to the Chainlit AMA server (run_ama.sh); same config, port 8001.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

export DYNAGENT_CONFIG_ROOT_DIR="${DYNAGENT_CONFIG_ROOT_DIR:-agent_configs/ama}"
export AGENTS_CONFIG_FILENAME="${AGENTS_CONFIG_FILENAME:-deep-agents.yaml}"

PORT="${PORT:-8001}"
export PORT

echo "Starting AMA web (AG-UI) on http://localhost:$PORT"
echo "Config directory: $DYNAGENT_CONFIG_ROOT_DIR (file: $AGENTS_CONFIG_FILENAME)"
echo "Resource plane: /threads /skills /tools /mcp-servers · Stream: /agent · Health: /health"

python -m autobots_agents_mer.domains.ama.web
```

- [ ] **Step 3: Make the script executable**

Run: `chmod +x sbin/run_ama_web.sh`

- [ ] **Step 4: Verify the entry point imports (no serve)**

Run: `../.venv/bin/python -c "import autobots_agents_mer.domains.ama.web.__main__ as m; print('bootstrap import ok')"`
Expected: `bootstrap import ok`

- [ ] **Step 5: Commit (from inside mer)**

```bash
git add sbin/run_ama_web.sh src/autobots_agents_mer/domains/ama/web/__main__.py
git commit -m "feat(ama-web): run_ama_web.sh + __main__ bootstrap on port 8001"
```

---

## Final verification (whole feature)

- [ ] **Step 1: shared-lib — run all new tests together**

Run (from shared-lib):
```bash
.venv/bin/pytest \
  tests/unit/test_thread_store_protocols.py tests/unit/test_resource_threads.py \
  tests/unit/test_skills_discovery.py tests/unit/test_resource_skills.py \
  tests/unit/test_resource_tools.py tests/unit/test_resource_mcp_servers.py \
  tests/unit/test_resource_router.py tests/unit/test_rail_stream.py \
  tests/unit/test_rail_stream_touch.py tests/unit/test_agui_endpoint.py \
  tests/unit/test_agui_app.py -q
```
Expected: all PASS.

- [ ] **Step 2: mer — run all new tests together**

Run (from mer):
```bash
../.venv/bin/pytest tests/unit/domains/test_ama_models.py \
  tests/unit/domains/test_ama_identity.py \
  tests/integration/domains/ama/test_thread_store_pg.py -q
```
Expected: all PASS.

- [ ] **Step 3: Lint + type-check both repos**

Run `make lint && make type-check` inside shared-lib, then inside mer.
Expected: ruff clean; pyright clean on all new modules.

- [ ] **Step 4: Live smoke (manual, needs Postgres + file-server + LLM key)**

```bash
# from mer, with MER_DATABASE_URL set and the file-server sidecar running:
./sbin/run_ama_web.sh &
curl -s localhost:8001/health                                   # {"status":"ok","graph":"assistant"}
curl -s -X POST localhost:8001/threads -H 'X-User-Id: alice' -H 'Content-Type: application/json' -d '{}'   # {"id":"..."}
curl -s localhost:8001/threads -H 'X-User-Id: alice'            # [{"id":...,"group":"Today",...}]
curl -s localhost:8001/skills  -H 'X-User-Id: alice'            # {"skills":[...],"warnings":[...]}
curl -s localhost:8001/tools   -H 'X-User-Id: alice'            # {"servers":[],"warnings":[]}  (AMA has no MCP servers yet)
curl -s localhost:8001/mcp-servers -H 'X-User-Id: alice'        # {"servers":[]}
```
Resolve **Open verification point 1** here: point the React UI (or a CopilotKit client) at `/agent`, switch `thread_id`, and confirm prior messages rehydrate from the checkpointer. If they do NOT, add a read-only `GET /threads/{id}/messages` calling `graph.aget_state({"configurable": {"thread_id": id}})` (new task, out of this plan's core scope).

---

## Open verification points (from spec §9 — resolve during implementation)

1. **CopilotKit rehydration on `thread_id` switch** — verified in Final Verification Step 4. Fallback: add `GET /threads/{id}/messages`.
2. **Stable skill-discovery entry point** — currently `deepagents.middleware.skills._alist_skills_with_errors` (underscore-private), isolated behind `discover_skills` (Task 3). If a public API appears, change only that import.
3. **MCP `access` READ/WRITE source** — Task 5 uses a write-verb name heuristic (`tool_access`). If MCP tool annotations become available on the loaded tool objects, prefer them inside `_describe_tool` and fall back to the heuristic.

---

## Self-Review

**Spec coverage:**
- §2/§3 scope A (streaming) → Tasks 8–10. B (activity rail) → existing `activity_projection`/`rail_stream`, hardened in Task 8. C (threads) → Tasks 1, 2, 12, 13. E (skills) → Tasks 3, 4. F (tools) → Task 5. MCP listing → Task 6. D (real connect) → deferred (Task 6 does display-only pref, as specified).
- §3.1 module layout → File Structure table matches (spike deleted in Task 10).
- §3.2 config (same env as Chainlit) → Task 14 `run_ama_web.sh`.
- §4 streaming plane (injected stores, config CORS, best-effort projection) → Tasks 8–10.
- §5.1 threads endpoints + auto-titling (frontend PATCH) → Task 2. §5.2 two-stores-one-key + DELETE clears checkpoint + touch on finish → Tasks 2 (checkpoint_deleter), 8 (touch hook), 13 (wiring). §5.3 skills live loader → Tasks 3, 4. §5.4 tools grouped + degrade → Task 5. §5.5 mcp-servers + display pref → Task 6. §5.6 PrefsStore → Tasks 1, 12.
- §6 identity (`resolve_user_id`, X-User-Id → DEFAULT_USER_ID) → Task 13; error handling (404/403/422 + degrade) → Tasks 2, 4, 5, 7.
- §7 testing (pure units, TestClient fakes, composition smoke, Postgres impls integration) → covered across tasks; new tests isolated in new files.
- §8 out-of-scope items → none implemented (Chainlit untouched; no OAuth; no LLM titles; no second transport).

**Type consistency:** `ThreadStore`/`PrefsStore`/`ThreadRecord`/`SkillInfo` signatures defined in Tasks 1/3 are reused verbatim in Tasks 2, 4, 6, 7, 12. `build_resource_router` keyword params match `create_agui_app`'s call (Task 10). `on_run_finished`/`checkpoint_deleter` names consistent across Tasks 2, 8, 9, 10, 13. `group_mcp_tools`/`tool_access`/`discover_skills`/`server_abbr` names consistent across producer and consumer tasks.

**Placeholder scan:** every code step contains complete, runnable code; every command has expected output. No TBD/TODO left.

**Deviations from spec (noted inline):**
- Added `ThreadStore.get` (spec omitted it) — needed for 403/404 ownership checks.
- Split pure helpers (`thread_group`, `tool_access`, `group_mcp_tools`, `server_abbr`) into their router modules so §7's pure-unit requirement is testable without a full app.
- Integration tests use in-process SQLite (store is DSN-agnostic) instead of an ephemeral Postgres sidecar, so they run in CI standalone; Postgres remains the production DSN. Registration via `SQLModel.metadata.create_all` is this repo's established "migration" (no Alembic present).
- `create_agui_app` takes an injectable `agent_factory` (default `create_base_deepagent`) purely to satisfy §7's "stub agent factory (no LLM)" smoke test.
