# FileServerBackend Lazy Context Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `FileServerBackend` from a build-time-snapshot object (constructed via a `runtime`-consuming factory) into a plain `BackendProtocol` instance that resolves its workspace context lazily and live from the context store on every file op, so `_build_fserver` returns an instance and the deepagents-0.7.0 callable-`backend=` deprecation is removed from our code.

**Architecture:** A `FileServerBackend` instance holds only an optional `context_key` *identity override*. On each file op it calls `_resolve()`, which reads `context_key` (instance override → ambient ContextVar), does a live `get_context(key)` store read, and passes the resulting store dict through a use-case-registered provider (`resolve_workspace_context`) that emits `{"workspace_base_path": ...}`. `session_id` comes from an existing ambient ContextVar (tracing metadata only, not path-affecting). MER registers the provider at AMA startup and sets the ambient `context_key` per request beside its existing `set_session_id` call.

**Tech Stack:** Python 3.12+, deepagents 0.6.12 (`BackendProtocol`), `contextvars.ContextVar`, httpx (sidecar client), pytest (`asyncio_mode = "auto"`), Ruff, Pyright (basic).

## Global Constraints

- **Python:** 3.12+ — one line each, exact values from repo config.
- **Ruff:** line-length 100, double quotes; rule set E, W, F, I, B, C4, UP, ARG, SIM, S, TCH, PTH, RET, TRY, PERF, RUF (ignore S101, E501, TRY003).
- **Type checker:** Pyright basic mode; monorepo config uses `venvPath = ".."`, `venv = ".venv"`.
- **Two repos, two commits:** shared-lib changes (Tasks 1–4) commit from inside `autobots-devtools-shared-lib/`; MER changes (Tasks 5–6) commit from inside `autobots-agents-mer/`. Pre-commit hooks run ruff + pyright + pytest + poetry check per repo.
- **Shared venv:** all commands run against `ws-autobots/.venv`. Activate with `source .venv/bin/activate` from workspace root, or call `../.venv/bin/pytest` etc.
- **Commit message trailer:** end every commit message with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **No callable ever reaches deepagents `backend=`:** after this work, no code path in either repo hands a callable/factory to deepagents as a backend.
- **shared-lib must not import MER:** path-formation business logic stays in MER and is injected via the provider seam.

---

## File Structure

**Shared-lib (`autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/`)**
- `common/observability/logging_utils.py` — add `get_session_id()` reader beside existing `set_session_id`.
- `common/observability/__init__.py` — export `get_session_id`.
- `common/utils/context_utils.py` — add ambient `context_key` ContextVar (`set_context_key`/`get_context_key`) and the workspace-context provider seam (`set_workspace_context_provider`/`resolve_workspace_context`).
- `dynagent/agents/fserver_backend.py` — `FileServerBackend` becomes lazy: new `__init__(context_key=None)`, new `_resolve()`, helpers resolve per call; delete `workspace_context_from_state` + `_WORKSPACE_CONTEXT_KEYS` + old ctor args.
- `dynagent/agents/deep_backend.py` — `_build_fserver` and `_build_composite` return instances (no factory closures); drop `workspace_context_from_state` import.

**Shared-lib tests (`autobots-devtools-shared-lib/tests/unit/`)**
- `test_fserver_backend.py` — migrate to lazy pattern.
- `test_deep_backend.py` — migrate fserver/composite build-site assertions to instances.

**MER (`autobots-agents-mer/src/autobots_agents_mer/`)**
- `common/utils/context_utils.py` — extract state-free `_workspace_context_from_ctx`, add `init_workspace_context_provider`, refactor `get_workspace_context` to delegate.
- `domains/ama/server.py` — register the provider at startup; set ambient `context_key` beside each `set_session_id`.

**MER tests (`autobots-agents-mer/tests/`)**
- `tests/unit/common/test_context_utils.py` — new: provider path formation + `get_workspace_context` delegation.
- `tests/integration/test_fserver_backend_live.py` — migrate constructor to no-arg.

---

## Task 1: `get_session_id()` public reader (shared-lib observability)

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/common/observability/logging_utils.py`
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/common/observability/__init__.py`
- Test: `autobots-devtools-shared-lib/tests/unit/test_logging_session_id.py` (create)

**Interfaces:**
- Consumes: existing module-private `_session_id_var: ContextVar[str]` (default `"default-session-id"`) and `set_session_id(session_id: str) -> None`.
- Produces: `get_session_id() -> str` — importable both from `...common.observability.logging_utils` and from `...common.observability`. Task 3 imports it into `fserver_backend`.

- [ ] **Step 1: Write the failing test**

Create `autobots-devtools-shared-lib/tests/unit/test_logging_session_id.py`:

```python
# ABOUTME: Unit tests for the ambient session-id reader.
# ABOUTME: Verifies get_session_id reflects set_session_id and the unset default.

from autobots_devtools_shared_lib.common.observability import (
    get_session_id,
    set_session_id,
)


def test_get_session_id_default_when_unset():
    # Fresh contextvar default sentinel (harmless for file ops per design).
    set_session_id("default-session-id")
    assert get_session_id() == "default-session-id"


def test_get_session_id_reflects_set():
    set_session_id("thread-42")
    assert get_session_id() == "thread-42"
    set_session_id("default-session-id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/pytest tests/unit/test_logging_session_id.py -v` (from `autobots-devtools-shared-lib/`)
Expected: FAIL — `ImportError: cannot import name 'get_session_id'`.

- [ ] **Step 3: Add `get_session_id` to `logging_utils.py`**

In `logging_utils.py`, immediately after the existing `set_session_id` function (ends at line 35), add:

```python
def get_session_id() -> str:
    """
    Return the session/thread identifier for the current context.

    Returns the "default-session-id" sentinel when unset; for file ops this is
    tracing metadata only and is harmless when defaulted.
    """
    return _session_id_var.get()
```

- [ ] **Step 4: Export it from the package `__init__.py`**

In `common/observability/__init__.py`, add `get_session_id` to both the import block and `__all__`:

```python
from autobots_devtools_shared_lib.common.observability.logging_utils import (
    SessionFilter,
    get_agent_logger,
    get_logger,
    get_session_id,
    set_log_level,
    set_session_id,
    setup_logging,
)
```

and in `__all__` add `"get_session_id",` (keep the list alphabetized — place it after `"get_agent_logger",`).

- [ ] **Step 5: Run test to verify it passes**

Run: `../.venv/bin/pytest tests/unit/test_logging_session_id.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit** (from inside `autobots-devtools-shared-lib/`)

```bash
git add src/autobots_devtools_shared_lib/common/observability/logging_utils.py \
        src/autobots_devtools_shared_lib/common/observability/__init__.py \
        tests/unit/test_logging_session_id.py
git commit -m "feat(observability): add get_session_id ambient reader

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Ambient `context_key` + workspace-context provider seam (shared-lib)

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/common/utils/context_utils.py`
- Test: `autobots-devtools-shared-lib/tests/unit/test_context_key_and_provider.py` (create)

**Interfaces:**
- Consumes: nothing new (adds module-level state).
- Produces, all importable from `...common.utils.context_utils`:
  - `set_context_key(key: str | None) -> None`
  - `get_context_key() -> str | None`
  - `set_workspace_context_provider(fn: Callable[[dict[str, Any]], dict[str, Any]] | None) -> None`
  - `resolve_workspace_context(ctx: dict[str, Any]) -> dict[str, Any]` — when a provider is registered, returns `provider(ctx)`; otherwise returns `ctx` unchanged (passthrough).
  These are **distinct** from the existing state-based `resolve_context_key` / `set_context_key_resolver` already in this module. Tasks 3, 5, and 6 consume these.

- [ ] **Step 1: Write the failing test**

Create `autobots-devtools-shared-lib/tests/unit/test_context_key_and_provider.py`:

```python
# ABOUTME: Unit tests for the ambient context_key var and workspace-context provider seam.
# ABOUTME: Distinct from the state-based resolve_context_key / set_context_key_resolver.

import pytest

from autobots_devtools_shared_lib.common.utils.context_utils import (
    get_context_key,
    resolve_workspace_context,
    set_context_key,
    set_workspace_context_provider,
)


@pytest.fixture(autouse=True)
def _reset():
    set_context_key(None)
    set_workspace_context_provider(None)
    yield
    set_context_key(None)
    set_workspace_context_provider(None)


def test_context_key_defaults_to_none():
    assert get_context_key() is None


def test_context_key_round_trips():
    set_context_key("user-7")
    assert get_context_key() == "user-7"
    set_context_key(None)
    assert get_context_key() is None


def test_resolve_workspace_context_passthrough_without_provider():
    ctx = {"user_name": "u", "repo_name": "r"}
    assert resolve_workspace_context(ctx) == ctx


def test_resolve_workspace_context_uses_registered_provider():
    set_workspace_context_provider(
        lambda ctx: {"workspace_base_path": f"{ctx['user_name']}/x"}
    )
    assert resolve_workspace_context({"user_name": "u"}) == {"workspace_base_path": "u/x"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/pytest tests/unit/test_context_key_and_provider.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_context_key'`.

- [ ] **Step 3: Add the ambient var and provider seam**

In `common/utils/context_utils.py`, add a `ContextVar` import to the existing `from contextvars import ...`? There is none yet — add a new import line near the top (after the existing `import json` on line 10). The file currently imports:

```python
import json
from collections.abc import Callable, Mapping
from typing import Any
```

Add `from contextvars import ContextVar` beneath `import json`. Then append the following block to the **end** of the file (after `resolve_workspace_context_for_file_api`, which currently ends at line 168):

```python
# --- Ambient context key (distinct from the state-based resolver above) -------
# Set per request by the Chainlit layer beside set_session_id(); read live by the
# deep-engine FileServerBackend to drive get_context(key) on every file op.
_context_key_var: ContextVar[str | None] = ContextVar("context_key", default=None)


def set_context_key(key: str | None) -> None:
    """Set the ambient context key for the current request/context."""
    _context_key_var.set(key)


def get_context_key() -> str | None:
    """Return the ambient context key, or None if unset."""
    return _context_key_var.get()


# --- Workspace-context provider seam (use-case-pluggable path formation) -------
# (store_context_dict) -> sidecar workspace_context dict, e.g. {"workspace_base_path": ...}
_workspace_context_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def set_workspace_context_provider(
    fn: Callable[[dict[str, Any]], dict[str, Any]] | None,
) -> None:
    """Register the use-case function that forms the sidecar workspace_context.

    Pass None to restore default passthrough behavior.
    """
    global _workspace_context_provider
    _workspace_context_provider = fn


def resolve_workspace_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Form the sidecar workspace_context from a store context dict.

    Uses the registered provider if set; otherwise passthrough so use-cases that
    already store a ready workspace_context dict keep working.
    """
    if _workspace_context_provider is not None:
        return _workspace_context_provider(ctx)
    return ctx
```

Note: `Callable`, `Any` are already imported at the top of the file; only `ContextVar` is new.

- [ ] **Step 4: Run test to verify it passes**

Run: `../.venv/bin/pytest tests/unit/test_context_key_and_provider.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit** (from inside `autobots-devtools-shared-lib/`)

```bash
git add src/autobots_devtools_shared_lib/common/utils/context_utils.py \
        tests/unit/test_context_key_and_provider.py
git commit -m "feat(context): add ambient context_key var and workspace-context provider seam

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `FileServerBackend` resolves context lazily (shared-lib)

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/fserver_backend.py`
- Test: `autobots-devtools-shared-lib/tests/unit/test_fserver_backend.py` (migrate)

**Interfaces:**
- Consumes: `get_session_id` (Task 1), `get_context_key` + `resolve_workspace_context` (Task 2), and the existing `get_context` from `...common.utils.context_utils`.
- Produces: `FileServerBackend(context_key: str | None = None)` — a `BackendProtocol` instance with no `session_id` / `workspace_context` constructor args and no `_session_id` / `_workspace_context` attributes. Adds `_resolve(self) -> tuple[str | None, dict[str, Any]]`. `workspace_context_from_state` and `_WORKSPACE_CONTEXT_KEYS` are **removed**. Task 4 (`deep_backend`) and Task 6 (integration test) depend on the no-arg / `context_key`-only constructor.

- [ ] **Step 1: Migrate the test file to the lazy pattern**

Edit `autobots-devtools-shared-lib/tests/unit/test_fserver_backend.py`.

(a) Replace the imports block at the top (lines 9–13) with:

```python
import autobots_devtools_shared_lib.dynagent.agents.fserver_backend as fb
from autobots_devtools_shared_lib.common.observability import set_session_id
from autobots_devtools_shared_lib.common.utils.context_utils import (
    set_context_key,
    set_workspace_context_provider,
)
from autobots_devtools_shared_lib.dynagent.agents.fserver_backend import FileServerBackend
```

(b) Add an autouse reset fixture immediately after the `_http_error` helper (before the `fake_store` fixture):

```python
@pytest.fixture(autouse=True)
def _reset_ambient():
    set_context_key(None)
    set_workspace_context_provider(None)
    set_session_id("default-session-id")
    yield
    set_context_key(None)
    set_workspace_context_provider(None)
    set_session_id("default-session-id")
```

(c) Delete the now-obsolete test `test_workspace_context_from_state_picks_known_keys` (currently lines 45–47) entirely.

(d) Replace the old `test_session_and_context_forwarded` (currently lines 114–124) with these three lazy-resolution tests:

```python
def test_resolve_forwards_ambient_context_and_session(monkeypatch):
    seen = {}

    def fake_list(base_path="", workspace_context=None, session_id=None):
        seen["workspace_context"] = workspace_context
        seen["session_id"] = session_id
        return []

    monkeypatch.setattr(fb, "raw_list_files", fake_list)
    monkeypatch.setattr(fb, "get_context", lambda key: {"loaded_for": key})
    monkeypatch.setattr(
        fb, "resolve_workspace_context", lambda ctx: {"workspace_base_path": "u/r-1"}
    )
    set_context_key("u1")
    set_session_id("sess-1")

    FileServerBackend().ls("/")

    assert seen == {
        "workspace_context": {"workspace_base_path": "u/r-1"},
        "session_id": "sess-1",
    }


def test_instance_context_key_overrides_ambient(monkeypatch):
    seen_keys = []

    def fake_get_context(key):
        seen_keys.append(key)
        return {}

    monkeypatch.setattr(
        fb, "raw_list_files", lambda base_path="", workspace_context=None, session_id=None: []
    )
    monkeypatch.setattr(fb, "get_context", fake_get_context)
    monkeypatch.setattr(fb, "resolve_workspace_context", lambda ctx: ctx)
    set_context_key("u1")

    FileServerBackend(context_key="u2").ls("/")

    assert seen_keys == ["u2"]


def test_no_context_key_yields_empty_workspace_and_skips_store(monkeypatch):
    seen = {}
    called = {"get_context": False}

    def fake_list(base_path="", workspace_context=None, session_id=None):
        seen["workspace_context"] = workspace_context
        return []

    def fake_get_context(key):
        called["get_context"] = True
        return {}

    monkeypatch.setattr(fb, "raw_list_files", fake_list)
    monkeypatch.setattr(fb, "get_context", fake_get_context)
    # No provider registered -> resolve_workspace_context is passthrough.

    FileServerBackend().ls("/")

    assert seen["workspace_context"] == {}
    assert called["get_context"] is False
```

- [ ] **Step 2: Run the migrated tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_fserver_backend.py -v`
Expected: FAIL — the new tests fail (e.g. `TypeError: 'workspace_context' is an unexpected keyword` is gone but `fb.get_context` / `fb.resolve_workspace_context` attributes don't exist yet, and `FileServerBackend(context_key=...)` is not accepted). Import of `workspace_context_from_state` is already removed, so no `ImportError` there.

- [ ] **Step 3: Rewrite the backend to resolve lazily**

Edit `fserver_backend.py`:

(a) Imports. Replace the two import blocks (lines 26–31) with:

```python
from autobots_devtools_shared_lib.common.observability import get_logger, get_session_id
from autobots_devtools_shared_lib.common.utils.context_utils import (
    get_context,
    get_context_key,
    resolve_workspace_context,
)
from autobots_devtools_shared_lib.common.utils.fserver_client_utils import (
    raw_list_files,
    raw_read_file,
    raw_write_file,
)
```

(b) Remove the now-unused `from collections.abc import Mapping` import (line 6) — `Mapping` is no longer referenced after deleting `workspace_context_from_state`. Keep `from typing import Any`.

(c) Delete the module-level `_WORKSPACE_CONTEXT_KEYS` constant (line 35) and the entire `workspace_context_from_state` function (lines 38–40).

(d) Replace the `__init__` and the three helpers (lines 55–75) with:

```python
    def __init__(self, context_key: str | None = None) -> None:
        # Identity override; None -> resolve from the ambient context_key ContextVar.
        self._context_key = context_key

    # -- lazy resolution ---------------------------------------------------

    def _resolve(self) -> tuple[str | None, dict[str, Any]]:
        """Resolve (session_id, workspace_context) live on each file op."""
        key = self._context_key or get_context_key()
        session_id = get_session_id()
        ctx = get_context(key) if key else {}
        if not key:
            logger.warning("FileServerBackend: no context_key available; workspace unscoped")
        workspace_context = resolve_workspace_context(ctx)
        return session_id, workspace_context

    # -- helpers -----------------------------------------------------------

    def _list_all(self) -> list[str]:
        session_id, workspace_context = self._resolve()
        files = raw_list_files("", workspace_context, session_id)
        return [str(f) for f in files]

    def _read_bytes(self, file_path: str) -> bytes:
        session_id, workspace_context = self._resolve()
        return raw_read_file(_to_server_path(file_path), workspace_context, session_id)

    def _write_bytes(self, file_path: str, content: bytes) -> None:
        session_id, workspace_context = self._resolve()
        raw_write_file(_to_server_path(file_path), content, workspace_context, session_id)
```

No other method bodies change — `ls/read/write/edit/glob/grep/upload_files/download_files` already route through `_list_all` / `_read_bytes` / `_write_bytes`, which now resolve per call.

- [ ] **Step 4: Run the full backend test file to verify it passes**

Run: `../.venv/bin/pytest tests/unit/test_fserver_backend.py -v`
Expected: PASS (all tests, including the 3 new lazy tests; the ~24 pre-existing direct/emulated-method tests pass unchanged because they set no context_key, so `_resolve` yields `({} , "default-session-id")` and the faked `raw_*` ignore both).

- [ ] **Step 5: Commit** (from inside `autobots-devtools-shared-lib/`)

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/fserver_backend.py \
        tests/unit/test_fserver_backend.py
git commit -m "feat(fserver): resolve workspace context lazily via ambient key + provider

Remove session_id/workspace_context ctor snapshots; FileServerBackend now
reads get_context(key) live on every op and forms workspace_context via the
use-case provider. Drops workspace_context_from_state and _WORKSPACE_CONTEXT_KEYS.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Collapse the backend factories to instances (shared-lib)

**Files:**
- Modify: `autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/deep_backend.py`
- Test: `autobots-devtools-shared-lib/tests/unit/test_deep_backend.py` (migrate)

**Interfaces:**
- Consumes: `FileServerBackend()` no-arg instance (Task 3), deepagents `CompositeBackend`, `StateBackend`, `BackendProtocol`.
- Produces: `_build_fserver(...) -> FileServerBackend` (instance); `_build_composite(...) -> CompositeBackend` (instance). `resolve_backend(...)` returns a `BackendProtocol` instance (never a callable) for every backend type. The `workspace_context_from_state` import is removed.

- [ ] **Step 1: Migrate the test file**

Edit `autobots-devtools-shared-lib/tests/unit/test_deep_backend.py`.

(a) Replace `test_fserver_type_returns_runtime_factory` (currently lines 44–50, plus the `_runtime` helper at lines 40–41 is still used by other tests — keep it) with:

```python
def test_fserver_type_returns_backend_instance():
    backend = resolve_backend({"type": "fserver"})
    assert isinstance(backend, FileServerBackend)
    assert backend._context_key is None
    assert not callable(getattr(backend, "__call__", None)) or isinstance(
        backend, FileServerBackend
    )
```

(Simpler assertion is fine — the key checks are `isinstance(..., FileServerBackend)` and `_context_key is None`.)

(b) Replace `test_composite_builds_routed_backend` (currently lines 74–89) with:

```python
def test_composite_builds_routed_backend():
    composite = resolve_backend(
        {
            "type": "composite",
            "routes": {
                "/workspace/": {"type": "fserver"},
                "/scratch/": {"type": "state"},
            },
        }
    )
    assert isinstance(composite, CompositeBackend)
    assert isinstance(composite.default, StateBackend)
    assert isinstance(composite.routes["/workspace/"], FileServerBackend)
    assert isinstance(composite.routes["/scratch/"], StateBackend)
```

(No `_runtime(...)` call and no `callable(...)` assertion — the result is now a live instance.)

(c) The `_runtime` helper (lines 40–41) is no longer referenced by any test after (a)/(b). Delete it and its no-longer-needed `from types import SimpleNamespace` import (line 4).

- [ ] **Step 2: Run the migrated tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_deep_backend.py -v`
Expected: FAIL — `test_fserver_type_returns_backend_instance` fails because `resolve_backend({"type": "fserver"})` currently returns a callable factory, not a `FileServerBackend`.

- [ ] **Step 3: Collapse `_build_fserver`**

In `deep_backend.py`, replace `_build_fserver` (lines 41–49) with:

```python
def _build_fserver(_cfg: dict[str, Any], **_kw: Any) -> FileServerBackend:
    return FileServerBackend()
```

- [ ] **Step 4: Collapse `_build_composite`**

Replace `_build_composite` (lines 52–70) with:

```python
def _build_composite(cfg: dict[str, Any], *, store: Any = None, **_kw: Any) -> CompositeBackend:
    route_configs = cfg.get("routes") or {}
    routes: dict[str, BackendProtocol] = {}
    for prefix, route_cfg in route_configs.items():
        backend = _build_backend(route_cfg, store=store)
        # _build_state returns None (deepagents' StateBackend default); every other
        # builder returns a BackendProtocol instance.
        routes[prefix] = backend if backend is not None else StateBackend()
    return CompositeBackend(default=StateBackend(), routes=routes)
```

- [ ] **Step 5: Drop the unused import**

In the import block (lines 12–15), remove `workspace_context_from_state` so it reads:

```python
from autobots_devtools_shared_lib.dynagent.agents.fserver_backend import (
    FileServerBackend,
)
```

- [ ] **Step 6: Run the deep_backend tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_deep_backend.py -v`
Expected: PASS (all tests, including override precedence, unknown-type, store-route, and the two migrated build-site tests).

- [ ] **Step 7: Run the full shared-lib backend suite together**

Run: `../.venv/bin/pytest tests/unit/test_deep_backend.py tests/unit/test_fserver_backend.py tests/unit/test_context_key_and_provider.py tests/unit/test_logging_session_id.py -v`
Expected: PASS (all four files green).

- [ ] **Step 8: Commit** (from inside `autobots-devtools-shared-lib/`)

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/deep_backend.py \
        tests/unit/test_deep_backend.py
git commit -m "refactor(deep_backend): return backend instances, not runtime factories

_build_fserver and _build_composite now return BackendProtocol instances; no
code path hands a callable to deepagents backend=, removing the 0.7.0
deprecation. Drops the workspace_context_from_state import.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: MER path provider (state-free core + registration)

**Files:**
- Modify: `autobots-agents-mer/src/autobots_agents_mer/common/utils/context_utils.py`
- Test: `autobots-agents-mer/tests/unit/common/test_context_utils.py` (create)

**Interfaces:**
- Consumes: shared-lib `set_workspace_context_provider` + `resolve_workspace_context` (Task 2), existing `get_context` (aliased `shared_get_context`) and `resolve_context_key`.
- Produces:
  - `_workspace_context_from_ctx(ctx: Mapping[str, Any], *, fallback_base: str | None) -> dict[str, Any]` — emits `{"workspace_base_path": "<user>/<repo>-<jira>"}` when all present; `{"workspace_base_path": "<user>/<fallback_base>"}` when repo/jira absent but user + `fallback_base` present; `{}` otherwise.
  - `init_workspace_context_provider(fallback_base: str | None = None) -> None` — registers the shared-lib provider using that core.
  - `get_workspace_context(state)` keeps its existing signature/return but delegates to the core with `fallback_base=None`. Task 6 calls `init_workspace_context_provider`.

- [ ] **Step 1: Write the failing test**

Create `autobots-agents-mer/tests/unit/common/test_context_utils.py`:

```python
# ABOUTME: Unit tests for MER workspace-context path formation and provider registration.
# ABOUTME: Covers _workspace_context_from_ctx, init_workspace_context_provider, get_workspace_context.

import pytest

import autobots_agents_mer.common.utils.context_utils as mer_ctx
from autobots_agents_mer.common.utils.context_utils import (
    _workspace_context_from_ctx,
    get_workspace_context,
    init_workspace_context_provider,
)
from autobots_devtools_shared_lib.common.utils.context_utils import (
    resolve_workspace_context,
    set_workspace_context_provider,
)


@pytest.fixture(autouse=True)
def _reset_provider():
    set_workspace_context_provider(None)
    yield
    set_workspace_context_provider(None)


def test_from_ctx_full_triple():
    ctx = {"user_name": "alice", "repo_name": "svc", "jira_number": "J-9"}
    assert _workspace_context_from_ctx(ctx, fallback_base=None) == {
        "workspace_base_path": "alice/svc-J-9"
    }


def test_from_ctx_user_id_alias():
    ctx = {"user_id": "bob", "repo_name": "svc", "jira_number": "J-1"}
    assert _workspace_context_from_ctx(ctx, fallback_base=None) == {
        "workspace_base_path": "bob/svc-J-1"
    }


def test_from_ctx_fallback_when_no_repo_or_jira():
    ctx = {"user_name": "carol"}
    assert _workspace_context_from_ctx(ctx, fallback_base="AMA-MER-1") == {
        "workspace_base_path": "carol/AMA-MER-1"
    }


def test_from_ctx_empty_without_fallback():
    ctx = {"user_name": "dave"}
    assert _workspace_context_from_ctx(ctx, fallback_base=None) == {}


def test_from_ctx_empty_without_user():
    ctx = {"repo_name": "svc", "jira_number": "J-1"}
    assert _workspace_context_from_ctx(ctx, fallback_base="AMA-MER-1") == {}


def test_init_provider_registers_shared_resolver():
    init_workspace_context_provider(fallback_base="AMA-MER-1")
    assert resolve_workspace_context({"user_name": "erin"}) == {
        "workspace_base_path": "erin/AMA-MER-1"
    }


def test_get_workspace_context_uses_store_no_fallback(monkeypatch):
    monkeypatch.setattr(mer_ctx, "resolve_context_key", lambda state: "key-1")
    monkeypatch.setattr(
        mer_ctx,
        "shared_get_context",
        lambda key: {"user_name": "u", "repo_name": "r", "jira_number": "J-2"},
    )
    assert get_workspace_context({"anything": True}) == {"workspace_base_path": "u/r-J-2"}


def test_get_workspace_context_falls_back_to_state(monkeypatch):
    monkeypatch.setattr(mer_ctx, "resolve_context_key", lambda state: "key-1")
    monkeypatch.setattr(mer_ctx, "shared_get_context", lambda key: {})
    state = {"user_name": "u", "repo_name": "r", "jira_number": "J-3"}
    assert get_workspace_context(state) == {"workspace_base_path": "u/r-J-3"}


def test_get_workspace_context_none_state_returns_empty():
    assert get_workspace_context(None) == {}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../.venv/bin/pytest tests/unit/common/test_context_utils.py -v` (from `autobots-agents-mer/`)
Expected: FAIL — `ImportError: cannot import name '_workspace_context_from_ctx'`.

- [ ] **Step 3: Rewrite MER `context_utils.py`**

Replace the entire body of `autobots-agents-mer/src/autobots_agents_mer/common/utils/context_utils.py` with:

```python
# ABOUTME: MER common context utilities — get_workspace_context + shared-lib provider wiring.
# ABOUTME: Forms workspace_base_path as "<user>/<repo>-<jira>" (with per-domain fallback).

from collections.abc import Mapping
from typing import Any

from autobots_devtools_shared_lib.common.utils.context_utils import (
    get_context as shared_get_context,
)
from autobots_devtools_shared_lib.common.utils.context_utils import (
    resolve_context_key,
    set_context_key_resolver,
    set_workspace_context_provider,
)


def init_context_key_resolver() -> None:
    """Register a context_key_resolver that extracts user_name from agent state.

    Must be called once at startup (e.g. from orchestrator or app init) so that
    get_workspace_context() can look up the correct context from the store using
    the user_name stored in runtime.state.
    """
    set_context_key_resolver(lambda state: state.get("user_name") or "default")


def _workspace_context_from_ctx(
    ctx: Mapping[str, Any], *, fallback_base: str | None
) -> dict[str, Any]:
    """Form the sidecar workspace_context from a context/state dict.

    Returns {"workspace_base_path": "<user>/<repo>-<jira>"} when user+repo+jira are
    present. When repo/jira are absent but a fallback_base is given (no-repo/jira
    domains such as AMA), returns {"workspace_base_path": "<user>/<fallback_base>"}.
    Returns {} when the user cannot be determined (or no fallback applies).
    """
    user = (ctx.get("user_name") or ctx.get("user_id") or "").strip()
    repo = (ctx.get("repo_name") or "").strip()
    jira = (ctx.get("jira_number") or "").strip()
    if user and repo and jira:
        return {"workspace_base_path": f"{user}/{repo}-{jira}"}
    if user and fallback_base:
        return {"workspace_base_path": f"{user}/{fallback_base}"}
    return {}


def init_workspace_context_provider(fallback_base: str | None = None) -> None:
    """Register the shared-lib workspace-context provider for this domain/process.

    The deep-engine FileServerBackend calls the registered provider on each file op
    to turn the loaded store context into a sidecar workspace_context dict.
    """
    set_workspace_context_provider(
        lambda ctx: _workspace_context_from_ctx(ctx, fallback_base=fallback_base)
    )


def get_workspace_context(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return workspace context from the store (classic engine path).

    Resolves context_key from state, loads the store context, and forms
    {"workspace_base_path": "user/repo-jira"}. Falls back to forming directly from
    state when the store has no usable context (e.g. script invocation). Classic
    engine paths (nurture/designer) require real repo/jira, so no fallback_base.

    Args:
        state: Agent state dict (e.g. runtime.state); used to resolve context_key.

    Returns:
        Dict with workspace_base_path, or empty dict if context cannot be resolved.
    """
    if state is None:
        return {}
    context_key = resolve_context_key(state)
    ctx = shared_get_context(context_key)
    from_store = _workspace_context_from_ctx(ctx, fallback_base=None)
    if from_store:
        return from_store
    return _workspace_context_from_ctx(state, fallback_base=None)
```

Note: `shared_get_context` and `resolve_context_key` are referenced as module attributes so the tests can `monkeypatch.setattr(mer_ctx, ...)`. `init_context_key_resolver` is preserved unchanged (still used by nurture/designer).

- [ ] **Step 4: Run the test to verify it passes**

Run: `../.venv/bin/pytest tests/unit/common/test_context_utils.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit** (from inside `autobots-agents-mer/`)

```bash
git add src/autobots_agents_mer/common/utils/context_utils.py \
        tests/unit/common/test_context_utils.py
git commit -m "feat(mer/context): state-free path core + workspace-context provider

Extract _workspace_context_from_ctx (with per-domain fallback), add
init_workspace_context_provider to register the shared-lib provider, and have
get_workspace_context delegate to the same core (fallback_base=None).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: AMA front-end wiring + integration-test migration (MER)

**Files:**
- Modify: `autobots-agents-mer/src/autobots_agents_mer/domains/ama/server.py`
- Modify: `autobots-agents-mer/tests/integration/test_fserver_backend_live.py`

**Interfaces:**
- Consumes: shared-lib `set_context_key` (Task 2), MER `init_workspace_context_provider` (Task 5), existing `get_user_identifier()` (returns the same string used as the context-store key by `update_workspace_context`), `FileServerBackend()` no-arg (Task 3).
- Produces: at AMA startup the provider is registered with the AMA fallback; on every request the ambient `context_key` is set to the user id beside `set_session_id`.

**Context (verified):** `update_workspace_context` writes the store under `user_id = get_user_identifier()`, and AMA's `deep-agents.yaml` uses `default_backend: {type: fserver}`. So `context_key == user_id == get_user_identifier()` — the store key the settings form writes under. This satisfies spec §8's identity check.

- [ ] **Step 1: Add imports to `ama/server.py`**

In `ama/server.py`, the shared-lib observability import block is at lines 8–14. Leave it as-is (it already imports `set_session_id`). Add two new imports.

After the shared-lib import block (after line 16, `from autobots_devtools_shared_lib.dynagent.ui import stream_agent_events`), add:

```python
from autobots_devtools_shared_lib.common.utils.context_utils import set_context_key
```

In the MER import group (near line 20, `from autobots_agents_mer.common.utils.chainlit_utils import get_user_identifier`), add:

```python
from autobots_agents_mer.common.utils.context_utils import init_workspace_context_provider
```

- [ ] **Step 2: Register the provider at module startup**

In `ama/server.py`, the module-level startup calls are at lines 37–40 (`init_ama_settings()`, `register_health_endpoint()`). Immediately after `register_health_endpoint()` (line 40), add:

```python
# Register the workspace-context provider for the deep-engine file backend.
# Fallback base path for no-repo/jira AMA workspaces; override via env if needed.
AMA_WORKSPACE_FALLBACK = os.getenv("AMA_WORKSPACE_FALLBACK", "AMA-MER-1")
init_workspace_context_provider(fallback_base=AMA_WORKSPACE_FALLBACK)
```

(`os` is already imported at line 4.)

- [ ] **Step 3: Set the ambient context_key in `on_chat_start`**

In `on_chat_start`, `user_id` is computed at line 81 and `set_session_id(...)` is called at line 91. Immediately after the `set_session_id(cl.context.session.thread_id)` line (line 91), add:

```python
    set_context_key(user_id)
```

- [ ] **Step 4: Set the ambient context_key in `on_message`**

In `on_message`, `set_session_id(cl.context.session.thread_id)` is at line 101. Immediately after it, add:

```python
    set_context_key(get_user_identifier())
```

(`get_user_identifier()` is idempotent and returns the same id set at chat start / stored under `user_id`.)

- [ ] **Step 5: Migrate the live integration test constructor**

In `autobots-agents-mer/tests/integration/test_fserver_backend_live.py`, line 28 currently reads:

```python
    backend = FileServerBackend(session_id=f"it-{uuid.uuid4().hex[:8]}")
```

Replace it with:

```python
    backend = FileServerBackend()
```

The `import uuid` (line 5) is still used for the `directory`/`path` names, so leave it. The test remains `skipif` when the sidecar is down; with no context_key set it exercises an unscoped workspace, exactly as the old `session_id`-only construction did.

- [ ] **Step 6: Verify the edited server module is syntactically valid and correctly wired**

The server module is a Chainlit entry point; drive it with static checks rather than importing under a live Chainlit context.

Run: `../.venv/bin/python -m py_compile src/autobots_agents_mer/domains/ama/server.py`
Expected: exit 0, no output.

Run: `../.venv/bin/ruff check src/autobots_agents_mer/domains/ama/server.py`
Expected: PASS (no lint errors).

Run: `grep -n "set_context_key" src/autobots_agents_mer/domains/ama/server.py`
Expected: exactly two call-site lines (`set_context_key(user_id)` in `on_chat_start`, `set_context_key(get_user_identifier())` in `on_message`) plus the import line.

- [ ] **Step 7: Verify the integration test still collects (skips without sidecar)**

Run: `../.venv/bin/pytest tests/integration/test_fserver_backend_live.py -v`
Expected: 1 skipped (sidecar not reachable) — or PASS if a sidecar is running. No collection/constructor error.

- [ ] **Step 8: Commit** (from inside `autobots-agents-mer/`)

```bash
git add src/autobots_agents_mer/domains/ama/server.py \
        tests/integration/test_fserver_backend_live.py
git commit -m "feat(ama): register workspace-context provider and set ambient context_key

Register init_workspace_context_provider (fallback AMA-MER-1) at startup and set
set_context_key(user_id) beside set_session_id in on_chat_start/on_message.
Migrate the live fserver integration test to the no-arg constructor.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Full-suite verification + deprecation-free confirmation

**Files:** none (verification only).

- [ ] **Step 1: Run the shared-lib unit suite**

Run (from `autobots-devtools-shared-lib/`): `make test`
Expected: PASS. Pay attention to `test_deep_backend.py`, `test_fserver_backend.py`, `test_context_key_and_provider.py`, `test_logging_session_id.py`.

- [ ] **Step 2: Run the MER unit suite**

Run (from `autobots-agents-mer/`): `../.venv/bin/pytest tests/unit -v`
Expected: PASS, including `tests/unit/common/test_context_utils.py`.

- [ ] **Step 3: Confirm no callable is handed to deepagents `backend=`**

Run (from `ws-autobots/`):
```bash
grep -rn "def factory" autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/deep_backend.py
grep -rn "workspace_context_from_state\|_WORKSPACE_CONTEXT_KEYS" \
  autobots-devtools-shared-lib/src autobots-agents-mer/src
```
Expected: both greps return **no matches** — the factory closures and the deleted helper/constant are gone.

- [ ] **Step 4: Type-check both repos**

Run (from `autobots-devtools-shared-lib/`): `make type-check`
Run (from `autobots-agents-mer/`): `make type-check`
Expected: PASS (Pyright basic, no new errors in the touched files).

- [ ] **Step 5: Format + lint check both repos**

Run (from `autobots-devtools-shared-lib/`): `make check-format`
Run (from `autobots-agents-mer/`): `make check-format`
Expected: PASS.

No commit — this task only verifies the aggregate state produced by Tasks 1–6.

---

## Self-Review

**Spec coverage:**
- §4.1 ambient `context_key` + provider seam → Task 2. ✓
- §4.2 `get_session_id()` + export → Task 1. ✓
- §4.3 `FileServerBackend` lazy `_resolve`, deletions of `workspace_context_from_state` / `_WORKSPACE_CONTEXT_KEYS` / old ctor args → Task 3. ✓
- §4.4 collapse `_build_fserver` / `_build_composite` to instances, remove import, no callable to deepagents → Task 4 (+ Task 7 Step 3 confirms). ✓
- §4.5 MER `_workspace_context_from_ctx` + `init_workspace_context_provider` + `get_workspace_context` delegation → Task 5. ✓
- §4.6 AMA wiring: provider registration with `AMA_WORKSPACE_FALLBACK`, `set_context_key` beside `set_session_id` → Task 6. ✓
- §6 Testing: lazy resolution, instance override wins, no-provider/no-key passthrough, build sites, MER provider, regression migration → covered across Tasks 3, 4, 5, 6. ✓
- §8 checks: `context_key == user_id == get_context` store key confirmed in Task 6 context note; every `set_session_id` deep entrypoint (AMA `on_chat_start`/`on_message`) gets `set_context_key` (Task 6). Sidecar accepts `{"workspace_base_path": ...}` for ls/glob/grep — same payload path `mer_read_file`/`mer_write_file` already use; the live roundtrip test (Task 6) exercises write/read/ls/edit/grep. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; every command has expected output.

**Type consistency:** `_resolve() -> tuple[str | None, dict[str, Any]]`, `FileServerBackend(context_key: str | None = None)`, `_workspace_context_from_ctx(ctx, *, fallback_base)`, `init_workspace_context_provider(fallback_base=None)`, `set_context_key(key: str | None)`, `get_context_key() -> str | None`, `resolve_workspace_context(ctx) -> dict[str, Any]`, `get_session_id() -> str` — names/signatures consistent across Tasks 1–6.

**Note on scope of `set_session_id` call sites:** the design (§8) asks to wire `set_context_key` at **deep-engine** entrypoints. Only AMA runs the deep engine today (its `deep-agents.yaml` uses `fserver`). The many `set_session_id` sites in `demo`/`nurture`/`designer` use the **classic** engine + `mer_read_file`/`get_workspace_context` path (unchanged by this work), so they intentionally do **not** get `set_context_key`. If/when another domain adopts the deep engine, add `set_context_key` there too (out of scope here per §7).
