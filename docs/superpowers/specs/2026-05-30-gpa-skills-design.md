# General Purpose Agent (GPA) with Skills — Design

**Date:** 2026-05-30
**Status:** Approved for planning
**Author:** PK (with Claude Code)

## 1. Purpose

Give FBP developers a **General Purpose Agent (GPA)** for day-to-day operations,
extensible through user-authored **Skills**. A skill is a `SKILL.md` playbook (plus
optional supporting files) that the agent discovers and loads on demand. Canonical
first skill: *"convert a conversation into an EDN mapper."*

Skills follow the deepagents Skills model: progressive disclosure (the agent sees
only skill name+description up front, loads the full `SKILL.md` when a skill matches),
served from a list of source paths with last-one-wins override.

## 2. Key Decisions (locked during brainstorming)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Adopt `deepagents`** for the GPA via `create_deep_agent`; keep existing `create_agent`/`create_base_agent` for current domains. Migration of domains is a later, deliberate effort. | Honest expression of "adopt deepagents." `SkillsMiddleware` alone still requires `FilesystemMiddleware`+backend, i.e. ~80% of `create_deep_agent` hand-wired and owned forever. |
| 2 | Skills live on the **fserver** (runtime), authored/uploaded at runtime — not in git. | Developers add/update skills with no redeploy. |
| 3 | **Two skill scopes**, `skills=["/skills/team", "/skills/user"]` (user listed last → wins on name collision). | Team-shared library + per-developer beta, no extra moving parts beyond scope routing. |
| 4 | **User scope keyed on `Dynagent.user_name`** (stable across a developer's sessions). | Beta skills persist across sessions; enables a promotion gate. |
| 5 | **GPA hosted in the MER consumer app**; **`FserverBackend` adapter lives in shared-lib**. | GPA is developer-facing (MER = SDLC/dev workflows). Backend is the reusable piece for the later domain migration. |
| 6 | Entry via **Chainlit + agent self-authoring**: developer describes a skill in chat, GPA writes `SKILL.md` to its user scope. | No new endpoints; lowest friction. |
| 7 | **MVP1 = playbooks** (instructions-only, `write` create-only, no code execution). **MVP2 = scripts** (needs a sandbox backend). | De-risk; MVP1 backend interface extends to MVP2 without breaking changes. |

## 3. Architecture

```
Chainlit UI (MER)
   │  invoke with state: { session_id, user_name, ... }
   ▼
GPA graph  =  create_deep_agent(
                 model      = lm(),                       # shared-lib LLM factory
                 middleware = [inject_agent_*],           # shared-lib prompt injector (reused)
                 skills     = ["/skills/team", "/skills/user"],
                 backend    = gpa_backend_factory,        # BackendFactory → per-invocation
                 state_schema = GpaState,                 # DeepAgentState + session_id + user_name
                 checkpointer = ...,
                 name       = "gpa",
              )
   │  deepagents auto-attaches: FilesystemMiddleware (ls/read/write/edit/glob/grep tools),
   │  SkillsMiddleware (skill menu + on-demand load), Todo/SubAgent/Summarization
   ▼
gpa_backend_factory(runtime) → CompositeBackend routing:
     "/skills/team"  → FserverBackend(scope = shared team workspace_context)
     "/skills/user"  → FserverBackend(scope = user_name workspace_context)
     "/"      (else) → FserverBackend(scope = session working area)
   │
   ▼  ls/read/write/edit  ──REST──▶  fserver
        (list_files / read_file / write_file / move_file)
```

Existing dynagent (`create_base_agent`, all MER/Jarvis/Pay domains) is **untouched**.

MER wiring note: MER exposes each domain agent from a per-domain FastAPI `server.py`
that registers usecase tools and builds the agent in `lifespan` (see
`domains/designer/server.py`). The GPA follows the same pattern with its own
`server.py` building the GPA via `create_gpa_agent()` instead of `create_base_agent`.
MER package root is `autobots_agents_mer`; Python 3.12; depends on
`autobots-devtools-shared-lib` (local `develop=true` path dep, currently `>=0.6.0`).

## 4. Components

### 4.1 `FserverBackend(BackendProtocol)` — shared-lib (new `dynagent/backends/` package)

Adapts shared-lib's existing fserver client (`common/utils/fserver_client_utils.py`)
to deepagents' `BackendProtocol`. **Scope is baked into the instance** (mirrors the
`S3Backend(bucket, prefix)` pattern): each instance carries a fixed
`workspace_context` + `session_id`, because `BackendProtocol` methods take no scope
args. All methods are **sync** (matches the protocol).

Method mapping (protocol → fserver client):

| BackendProtocol | fserver client | Notes |
|---|---|---|
| `ls(path) -> LsResult` | `list_files(path, ctx, session_id)` | Parse listing (client returns `str(files)`) into `FileInfo` entries. |
| `read(file_path, offset=0, limit=2000) -> ReadResult` | `read_file(name, ctx, session_id)` | Slice to `[offset:offset+limit]` lines; client already base64-handles binary; on error → `ReadResult(error=...)`. |
| `write(file_path, content) -> WriteResult` | `write_file(...)` | **Create-only**: `ls`-check first; error if exists. `WriteResult(path=..., files_update=None)`. |
| `edit(file_path, old, new, replace_all=False) -> EditResult` | `read_file` + `write_file` | Read → replace (enforce uniqueness unless `replace_all`) → write; return occurrence count. |
| `grep(pattern, path=None, glob=None) -> GrepResult` | `ls` + read + in-process scan | No server-side search today. |
| `glob(pattern, path="/") -> GlobResult` | `ls` + fnmatch | Client-side pattern match. |

**Caching:** short-TTL (≈30–60s) cache inside the backend keyed by
`(workspace_context, path)` for `ls`/`read`, so progressive-disclosure menu building
doesn't cost `1 ls + N reads` per scope on every turn.

**Reference (`BackendProtocol` shape, sync):**

```python
from deepagents.backends.protocol import (
    BackendProtocol, WriteResult, EditResult, LsResult, ReadResult, GrepResult, GlobResult,
)

class FserverBackend(BackendProtocol):
    def __init__(self, workspace_context: str, session_id: str | None): ...
    def ls(self, path: str) -> LsResult: ...
    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult: ...
    def write(self, file_path: str, content: str) -> WriteResult: ...          # create-only
    def edit(self, file_path: str, old_string: str, new_string: str,
             replace_all: bool = False) -> EditResult: ...
    def grep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult: ...
    def glob(self, pattern: str, path: str = "/") -> GlobResult: ...
```

### 4.2 Scope routing — `CompositeBackend`

A `CompositeBackend` routes `/skills/team`, `/skills/user`, and the default working
area to three `FserverBackend` instances with different scopes. Team scope = a fixed,
session-independent `workspace_context`. User scope = `workspace_context` derived from
`user_name`. Default = session working area.

### 4.3 `gpa_backend_factory` (BackendFactory) — MER

User scope depends on `user_name`, so the backend cannot be a singleton.
`create_deep_agent` accepts `backend: BackendProtocol | BackendFactory`; we pass a
factory that reads `session_id` + `user_name` from runtime state and builds the
`CompositeBackend` per invocation.

### 4.4 `GpaState` — MER

`create_deep_agent` defaults to `DeepAgentState`. GPA needs a small subclass adding
`session_id` and `user_name` (the routing keys the factory consumes). This diverges
slightly from `Dynagent` (which carries the same fields atop `AgentState`); the
divergence is intentional and documented.

### 4.5 GPA wiring + config — MER

- `create_gpa_agent()` factory wrapping `create_deep_agent` (parallel to how domains
  call `create_base_agent`), wired from a GPA `server.py` `lifespan` like other MER
  domains.
- GPA prompt + `agent_configs/gpa/` (agent definition, authoring instructions),
  consistent with MER's existing `agent_configs/<domain>` layout and
  `DYNAGENT_CONFIG_ROOT_DIR`.
- Chainlit entry exposing the GPA.
- **Authoring prompt**: teaches the GPA to write a well-formed `SKILL.md`
  (frontmatter: `name`, `description`) to `/skills/user/<name>/` on request.

### 4.6 Promotion / write-gate (team-skill safety)

Authoring writes **only** to `/skills/user`. Promotion to `/skills/team` is a
**deliberate, separate action** (a `move_file`-backed step gated to the author),
**not** something the model does mid-chat. Prevents a half-baked beta from silently
shadowing a team skill via last-wins. The team scope is not generally writable by the
agent.

## 5. Data Flow — authoring & using a skill

1. **Author.** Developer: "make a skill that converts a conversation to an EDN mapper."
   GPA writes `SKILL.md` (correct frontmatter) to `/skills/user/edn-mapper/` via the
   backend (`write`, create-only).
2. **Discover.** Next turn, `SkillsMiddleware` lists both scopes, reads frontmatter,
   injects the name+description menu into the system prompt (served from cache).
3. **Use.** Developer asks for an EDN mapping. The model recognizes the skill from its
   description, calls the filesystem read tool to load the full `SKILL.md`, follows it.
4. **Promote (optional, gated).** Author runs the explicit promotion step → skill
   moves user → team; now visible to all; last-wins resolution applies.

## 6. Error Handling

- fserver errors surface as `ReadResult(error=...)` / `WriteResult` errors, not raised
  through the protocol (matches deepagents expectations).
- `write` on an existing path → create-only error (no silent overwrite).
- `edit` with a non-unique `old_string` and `replace_all=False` → error with
  occurrence count.
- Missing/empty `user_name` → user scope falls back to a safe per-session area (never
  writes into team scope).
- Cache is best-effort; a cache miss/expiry just re-fetches.

## 7. MVP Split

**MVP1 (playbooks):** `FserverBackend` (`ls/read/write/edit/glob/grep` + create-only +
cache), `CompositeBackend` scope routing, `gpa_backend_factory`, `GpaState`,
`create_gpa_agent` + config + Chainlit entry, agent self-authoring to user scope,
explicit gated promotion. **No code execution.**

**MVP2 (scripts):** skills bundle runnable `.py`; requires a `SandboxBackendProtocol`
backend (fserver alone can't safely execute). Explicitly deferred; MVP1 backend
interface extends without breaking changes.

## 8. Testing

- **Unit (shared-lib):** `FserverBackend` against a mocked fserver client — every
  protocol method, create-only `write`, `edit` uniqueness / `replace_all`,
  `ls`/`grep`/`glob` mapping, cache TTL behavior.
- **Integration:** `CompositeBackend` routes team vs. user to the correct
  `workspace_context`; `create_deep_agent` boots with `lm()` + `inject_agent` + factory.
- **E2E:** the "conversation → EDN mapper" skill — author it, menu shows it, invoke it,
  full `SKILL.md` loads on demand and is followed; plus a promotion test (user → team,
  then last-wins resolution).

## 9. Dependencies / Risks

- **`deepagents` is a new dependency** (not in lock). Add to MER (and shared-lib for
  the backend protocol import). Verify it resolves against pinned `langchain>=1.0`,
  `langgraph`, Python 3.12.
- **Remote-store cost** of progressive disclosure — mitigated by the TTL cache.
- **Team-scope poisoning** — mitigated by author-only authoring + gated promotion.
- **State divergence** (`GpaState` vs `Dynagent`) — intentional and documented.
- `grep`/`glob` are client-side (no server search) — acceptable for skill-sized dirs.
- **API drift:** `create_deep_agent` signature and `BackendProtocol` are taken from
  current deepagents docs/source; pin the version and re-verify the signature at
  implementation time.

## 10. Out of Scope (MVP1)

Code execution / sandbox; non-Chainlit clients / dedicated GPA server; migrating
existing domains onto deepagents; server-side search.
