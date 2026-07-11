# FileServerBackend lazy context resolution — Design Spec

- **Date:** 2026-07-06
- **Repo:** `autobots-devtools-shared-lib` (with wiring in `autobots-agents-mer`)
- **Status:** Approved for planning

## 1. Problem

deepagents `0.5.0` deprecated — and `0.7.0` removes — passing a **callable factory** as
`backend` to `create_deep_agent` (see
`deepagents/middleware/filesystem.py::FilesystemMiddleware._get_backend`, which emits a
`warn_deprecated(since="0.5.0", removal="0.7.0")` whenever `callable(self.backend)`).

Our `_build_fserver` in `dynagent/agents/deep_backend.py` currently returns exactly such a
factory:

```python
def _build_fserver(_cfg, **_kw):
    def factory(runtime):
        state = getattr(runtime, "state", None) or {}
        return FileServerBackend(
            session_id=state.get("session_id"),
            workspace_context=workspace_context_from_state(state),
        )
    return factory
```

The factory exists so the backend can read `runtime.state` to build its workspace context.
Once the callable form is removed, `_build_fserver` must return a **`BackendProtocol`
instance**. But a backend instance's `ls/read/write/edit/glob/grep` methods receive **no
runtime** — so the instance cannot snapshot `session_id`/`workspace_context` from state. It
must resolve them **lazily, on each call**.

### Where the authoritative context lives, and the path convention

The *complete* workspace context is **not** in agent state. It lives in the **context store**
(`common/utils/context_utils.py::get_context(context_key)`), written by the Chainlit settings
form via `autobots_agents_mer/.../context_settings_utils.py::update_workspace_context`, keyed by
the user's `user_id`.

The file server does **not** take raw `{user_name, repo_name, jira_number}` keys as the path.
The working convention — used by `mer_read_file` / `mer_write_file` via
`autobots_agents_mer/.../context_utils.py::get_workspace_context` — is a **single precomputed
key**:

```
workspace_context = {"workspace_base_path": "<user_name>/<repo_name>-<jira_number>"}
```

The sidecar joins `<F-Server-App-Root>/<workspace_base_path>/<file>`. So designer and nurture
files live under `<root>/<user>/<repo>-<jira>/...`. `FileServerBackend` must emit this same
shape — **not** the raw keys that the old `workspace_context_from_state` produced.

### Precedent for lazy resolution

deepagents already solved the identical problem for `StateBackend`: construct the backend
**once**, and on each call reach the live execution through an **ambient handle**
(`get_config()` / `CONFIG_KEY_READ`) — see `deepagents/backends/state.py`.

Our shared-lib already has the same *ambient contextvar* precedent: `_session_id_var` /
`set_session_id()` in `common/observability/logging_utils.py`, set by the Chainlit layer per
request (e.g. AMA `on_message` calls `set_session_id(cl.context.session.thread_id)`).

## 2. Goal

Make `FileServerBackend` a plain `BackendProtocol` **instance** that resolves its workspace
context **lazily and live** from the context store — emitting the same `workspace_base_path`
shape as `get_workspace_context` — so `_build_fserver` returns an instance (not a factory), the
deepagents-`0.7.0` deprecation is fully removed from our code, and the future deep-engine batch
path is cleanly served.

## 3. Chosen approach — Approach A (ambient identity → live store read → use-case path provider)

On every file operation the backend resolves:

- a **`context_key`** — from an instance override if present, else from a new ambient
  `context_key` ContextVar; this key drives a **live** `get_context(key)` read of the store.
- a **`workspace_context`** — by passing the loaded store dict through a **use-case-registered
  provider** (`resolve_workspace_context`) that emits `{"workspace_base_path": ...}` following
  the domain's path convention (including the no-repo/jira fallback).
- a **`session_id`** — from the existing ambient `session_id` ContextVar (tracing metadata;
  **not** path-affecting — the path lives entirely in `workspace_base_path`).

Two resolution sources for `context_key`, by design:

| Surface | How `context_key` is supplied | Why it's safe |
|---|---|---|
| Interactive (Chainlit) | Ambient `context_key` ContextVar, set per request beside `set_session_id` | One shared graph serves many concurrent users; a request-scoped contextvar is the only correct per-user source |
| Batch (deep-engine future) | Explicit `FileServerBackend(context_key=user_id)` passed as `backend=` when building the batch's own graph | `batch_invoker` builds its **own** dedicated graph, so the backend instance is private to the batch; all records in a batch share one workspace, so one key is correct; no cross-thread contextvar propagation needed |

### Why an identity override, not a data snapshot

We **remove** the old `session_id` / `workspace_context` constructor args — those were *stale
data* snapshots taken at build time. We **add** a single `context_key` arg — a *stable
identity* that still drives a **live** `get_context(key)` on every call. The "always read the
store live" property is preserved; a mid-session settings edit takes effect on the next file op.

### Why a provider seam for path formation

The `<user>/<repo>-<jira>` convention and the AMA fallback are **use-case business logic** that
already lives in MER's `get_workspace_context`. shared-lib must not import MER, so it exposes a
DI seam and MER registers a provider that **reuses the same core** used by `mer_read_file` —
keeping one path convention across both the classic file tools and the deep backend.

## 4. Design detail

### 4.1 New shared-lib primitives — `common/utils/context_utils.py`

Ambient context key:

```python
from contextvars import ContextVar

_context_key_var: ContextVar[str | None] = ContextVar("context_key", default=None)
def set_context_key(key: str | None) -> None: _context_key_var.set(key)
def get_context_key() -> str | None: return _context_key_var.get()
```

Workspace-context provider seam (use-case-pluggable path formation):

```python
from collections.abc import Callable

# (store_context_dict) -> sidecar workspace_context dict
_workspace_context_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None

def set_workspace_context_provider(fn: Callable[[dict[str, Any]], dict[str, Any]] | None) -> None:
    global _workspace_context_provider
    _workspace_context_provider = fn

def resolve_workspace_context(ctx: dict[str, Any]) -> dict[str, Any]:
    if _workspace_context_provider is not None:
        return _workspace_context_provider(ctx)
    return ctx  # default passthrough: use-cases that store a ready dict still work
```

These are distinct from the existing state-based `resolve_context_key` / `set_context_key_resolver`.

### 4.2 New public accessor — `common/observability/logging_utils.py`

Add `get_session_id()` (only `set_session_id` exists today, plus the private `_session_id_var`
whose default is `"default-session-id"`) and export it from `common/observability/__init__.py`:

```python
def get_session_id() -> str:
    return _session_id_var.get()
```

The `"default-session-id"` sentinel when unset is harmless — `session_id` is tracing metadata
only for file ops.

### 4.3 `FileServerBackend` becomes lazy — `dynagent/agents/fserver_backend.py`

```python
class FileServerBackend(BackendProtocol):
    def __init__(self, context_key: str | None = None) -> None:
        self._context_key = context_key                       # identity override; None → ambient

    def _resolve(self) -> tuple[str | None, dict[str, Any]]:
        key = self._context_key or get_context_key()          # instance wins, else ambient
        session_id = get_session_id()
        ctx = get_context(key) if key else {}
        if not key:
            logger.warning("FileServerBackend: no context_key available; workspace unscoped")
        workspace_context = resolve_workspace_context(ctx)    # → {"workspace_base_path": ...}
        return session_id, workspace_context
```

Every direct/emulated method opens with `session_id, wc = self._resolve()` and passes those to
the `raw_*` helpers, replacing every use of `self._session_id` / `self._workspace_context`.

**Deletions:** `workspace_context_from_state()`, the `_WORKSPACE_CONTEXT_KEYS` constant, the old
`session_id` / `workspace_context` constructor args and instance attributes. `agent_name` is
gone from the workspace context — it was never in the store, is not path-critical, and the path
is fully expressed by `workspace_base_path`.

### 4.4 Collapse the factories — `dynagent/agents/deep_backend.py`

```python
def _build_fserver(_cfg, **_kw) -> FileServerBackend:
    return FileServerBackend()
```

In `_build_composite`, remove the `else: routes[prefix] = backend(runtime)` "materialize per
runtime" branch — every route is now a `BackendProtocol` instance — and return a
`CompositeBackend` **instance** instead of a `factory(runtime)`. Remove the now-unused
`workspace_context_from_state` import. After this change no repo code path hands a callable to
deepagents `backend=`.

### 4.5 MER path provider — `autobots_agents_mer/common/utils/context_utils.py`

Refactor the path core out of `get_workspace_context` so it is **state-free** and takes a
per-domain fallback, then have both `get_workspace_context` and the new provider use it:

```python
def _workspace_context_from_ctx(ctx: Mapping[str, Any], *, fallback_base: str | None) -> dict:
    user = (ctx.get("user_name") or ctx.get("user_id") or "").strip()
    repo = (ctx.get("repo_name") or "").strip()
    jira = (ctx.get("jira_number") or "").strip()
    if user and repo and jira:
        return {"workspace_base_path": f"{user}/{repo}-{jira}"}
    if user and fallback_base:                       # no-repo/jira domains (e.g. AMA)
        return {"workspace_base_path": f"{user}/{fallback_base}"}
    return {}

def init_workspace_context_provider(fallback_base: str | None = None) -> None:
    """Register the shared-lib workspace-context provider for this domain/process."""
    set_workspace_context_provider(lambda ctx: _workspace_context_from_ctx(ctx, fallback_base=fallback_base))
```

`get_workspace_context(state)` keeps its current signature/behavior but delegates to
`_workspace_context_from_ctx(ctx, fallback_base=None)` (classic engine paths — nurture/designer
— require real repo/jira, so no fallback).

### 4.6 Front-end wiring — `autobots-agents-mer`

At each deep-engine entrypoint that already calls `set_session_id(...)` (AMA `on_message`, and
any future deep domains), add one line — `context_key` **is** the `user_id`, which is also the
store key `update_workspace_context` writes under:

```python
set_session_id(thread_id)
set_context_key(user_id)     # NEW
```

At AMA startup (beside `init_context_key_resolver()`), register the provider with the AMA
fallback:

```python
AMA_WORKSPACE_FALLBACK = os.getenv("AMA_WORKSPACE_FALLBACK", "AMA-MER-1")  # per-domain configurable
init_workspace_context_provider(fallback_base=AMA_WORKSPACE_FALLBACK)
```

So AMA's `/AGENTS.md` resolves to `<root>/<user>/AMA-MER-1/AGENTS.md`, and `/skills/` under
`<root>/<user>/AMA-MER-1/skills/`. Changing the env (or constant) to `AMA` yields the flat
`<root>/<user>/AMA/...` form. `context_settings_utils.py` is unchanged.

## 5. Data flow (interactive, AMA)

```
Chainlit on_message ── set_context_key(user_id) ─▶ context_key ContextVar
                                                       │
assistant reads /AGENTS.md via fserver backend         │
        │                                              ▼
        └─▶ FileServerBackend._resolve()
                ├─ get_context_key()  → user_id
                ├─ get_session_id()   → thread_id
                ├─ get_context(user_id) → {user_name, repo_name?, jira_number?, ...}
                └─ resolve_workspace_context(ctx)  # MER provider, fallback "AMA-MER-1"
                        → {"workspace_base_path": "<user>/AMA-MER-1"}
            ─▶ raw_read_file("AGENTS.md", {"workspace_base_path": "<user>/AMA-MER-1"}, session_id)
```

## 6. Testing

- **Unit — lazy resolution (shared-lib):** with a stubbed store, a stub provider returning
  `{"workspace_base_path": "u/r-1"}`, and `set_context_key("u1")`, assert `ls/read/write` call
  the `raw_*` helpers with that dict and the ambient `session_id`.
- **Unit — instance override wins:** `FileServerBackend(context_key="u2")` resolves against `u2`
  even when the ambient var is `u1`.
- **Unit — no provider / no key:** default `resolve_workspace_context` is passthrough; with no
  key, `_resolve()` yields `{}`, logs the warning, and ops still call `raw_*` with `{}`.
- **Unit — build sites:** `_build_fserver(...)` returns a `FileServerBackend` **instance** (not
  callable); `_build_composite` returns a `CompositeBackend` instance; no path yields a callable.
- **Unit — MER provider (mer):** `_workspace_context_from_ctx` returns `"<u>/<r>-<j>"` when all
  present; `"<u>/AMA-MER-1"` when repo/jira absent but `fallback_base` set; `{}` when user absent
  or no fallback. Assert `get_workspace_context(state)` still passes `fallback_base=None`.
- **Regression:** migrate existing tests that construct
  `FileServerBackend(session_id=..., workspace_context=...)` to the ambient / `context_key` +
  provider pattern.

## 7. Out of scope

- Threading per-record `session_id` into the batch path (not path-affecting).
- Migrating `batch_invoker` to the deep engine (separate deep-engine-nurture-parity work); this
  spec only ensures the `context_key` constructor override exists for that future.
- Any change to `context_settings_utils.py` or the store schema.
- Declarative fallback in `deep-agents.yaml` (constant/env is sufficient now; yaml plumbing can
  come later if multiple deep domains diverge).

## 8. Risks / open checks for the plan

- Confirm `trace_metadata.user_id` equals the context-store key (`get_user_identifier()`) for the
  eventual batch wiring.
- Grep MER for every `set_session_id` call site and ensure each deep-engine entrypoint also gets
  `set_context_key`.
- Confirm the sidecar accepts `{"workspace_base_path": ...}` for `ls`/`glob`/`grep` (the emulated
  methods) as it does for `read`/`write` — `mer_read_file`/`mer_write_file` establish read/write;
  verify list is equivalent.
- `get_context` is a cache-backed (Redis/Postgres) read on every file op; workspace context is
  small and cached, so live reads are acceptable. Revisit with a per-`_resolve` memo only if
  profiling shows it matters.
