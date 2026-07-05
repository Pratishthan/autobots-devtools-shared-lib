# AMA UI Backend — Design Spec

**Date:** 2026-07-05
**Status:** Approved (design), pending implementation plan
**Scope owner:** shared-lib (`dynagent`), with concrete wiring in `autobots-agents-mer` (AMA domain)

## 1. Purpose

Build the Python servers and functions the **Dynagent AMA** React UI needs to
integrate with the deep-agent backend (`create_base_deepagent`). The React UI
itself is built separately and is **out of scope**; this spec covers only the
backend contract it consumes.

The UI is a three-pane workspace (mock + full behavioral spec in
`autobots-agents-mer/docs/design/dynagent_ama/README.md`):

- **Left rail** — conversation history, MCP servers, Skills.
- **Center** — chat thread + generative-UI result cards.
- **Right rail** — live agent-activity timeline + telemetry (tokens/tools/latency).

## 2. Scope

| # | UI surface | Backend need | In this cycle? |
|---|---|---|---|
| A | Center — chat stream + generative-UI cards | AG-UI/CopilotKit streaming over `create_base_deepagent` | **Yes** (productionize existing spike) |
| B | Right rail — activity timeline + telemetry | Derived `activity[]`/`stats{}` via `STATE_DELTA` | **Yes** (already implemented, relocate/clean) |
| C | Left rail — conversation history | Threads index API over the checkpointer | **Yes** |
| E | Left rail/modal — Skills gallery | Skills listing API | **Yes** (list = live; toggle = UI pref only) |
| F | Modal — MCP Tools browser | Tools introspection API | **Yes** (degrades gracefully) |
| D | Left rail — MCP **connect** / OAuth handshake | Real auth flow | **Deferred** — read-only server *listing* only |

**Decisions baked into scope:**
- Resource endpoints are **introspection-only**. Skill enable/disable and MCP
  "connected" are **persisted per-user UI preferences** that do NOT gate agent
  behavior this cycle.
- The new AG-UI/CopilotKit FastAPI app runs **in parallel** with the existing
  Chainlit AMA server (`domains/ama/server.py`); Chainlit is not retired.
- **Streaming stays AG-UI-only.** No second chat transport is built for
  non-UI clients this cycle (they can reuse `/agent` or call the agent library).

## 3. Architecture

Two planes share one `create_base_deepagent` graph + one Postgres checkpointer:

- **Streaming plane (AG-UI-specific)** — CopilotKit endpoint at `/agent`
  carrying chat tokens, tool-call lifecycle, generative-UI state, and the
  injected activity-rail `STATE_DELTA`.
- **Resource plane (client-agnostic)** — plain REST routers the React app (or
  any client: CLI, VS Code plugin, future frontend) calls: `/threads`,
  `/skills`, `/tools`, `/mcp-servers`.

The boundary is **client-agnostic vs. AG-UI-specific**, not "UI vs. not". The
resource plane knows nothing about CopilotKit/AG-UI, so it is reusable on its
own; `create_agui_app` merely *composes* the resource router with the AG-UI
streaming endpoint.

### 3.1 Module layout

```
shared-lib  src/autobots_devtools_shared_lib/dynagent/

  api/                         # CLIENT-AGNOSTIC — no CopilotKit/AG-UI imports
    thread_store.py            # ThreadStore + PrefsStore Protocols (DB-agnostic)
    skills_discovery.py        # discover_skills(meta, backend) wrapping deepagents
    resources/
      threads.py               # APIRouter: list / new / rename / delete
      skills.py                # APIRouter: list (+ enabled pref)
      tools.py                 # APIRouter: MCP tools grouped by server
      mcp_servers.py           # APIRouter: configured servers (+ connected pref)
    router.py                  # build_resource_router(meta, thread_store, prefs_store)

  ui/                          # AG-UI / CopilotKit-specific
    agui_endpoint.py           # mounts CopilotKit AG-UI streaming at /agent
    agui_app.py                # create_agui_app(...) = resource router + AG-UI endpoint
    rail_stream.py             # (kept) STATE_DELTA activity injection
    activity_projection.py     # (kept) pure reducer
    collapse_system_messages.py# (kept)
    # copilotkit_server.py spike DELETED — good parts fold into agui_app.py

mer  src/autobots_agents_mer/domains/ama/web/
  app.py                       # concrete app: Postgres stores + checkpointer +
                               # identity, calls create_agui_app(...)
  thread_store_pg.py           # Postgres ThreadStore + PrefsStore impls
mer  src/autobots_agents_mer/common/db/
  ama_threads + ama_user_prefs models + migration
mer  sbin/run_ama_web.sh       # new port (e.g. 8001), parallel to Chainlit (3340)
```

### 3.2 Config

The web app uses the **same config as Chainlit AMA**, no duplication.
`run_ama_web.sh` exports the same env vars:

```bash
export DYNAGENT_CONFIG_ROOT_DIR=agent_configs/ama
export AGENTS_CONFIG_FILENAME=deep-agents.yaml
```

`create_agui_app` → `create_base_deepagent()` → `AgentMeta.instance()` loads
`agent_configs/ama/deep-agents.yaml` (the `assistant` + `wiring-check` roster,
`skills: ["/skills/"]`, `memory: ["/AGENTS.md"]`, `fserver` backend). The two
servers are separate processes, each reading env at startup — no shared-singleton
conflict.

**Payoff:** `/skills`, `/tools`, `/mcp-servers` derive from that same live
`AgentMeta`, so the left rail shows exactly what the agent loaded — not a
hand-maintained parallel list. With AMA's current config (`tools: []`, no
`mcp_servers`), `/tools` and `/mcp-servers` legitimately return empty until
servers are added; the endpoints are structurally ready.

## 4. Streaming plane (A + B)

`create_agui_app` builds the graph once via
`create_base_deepagent(checkpointer=<Postgres saver>)` with
`middleware=[CopilotKitMiddleware(), collapse_system_messages]`, wraps it in
`RailAGUIAgent` (unchanged — it already injects the activity-rail `STATE_DELTA`),
and mounts it at `/agent` via `add_langgraph_fastapi_endpoint`. Langfuse callback
+ `recursion_limit` attached as today. This is the existing spike's logic,
cleaned to conventions: injected stores (not module-level `InMemorySaver`),
config-driven CORS origins, ABOUTME headers, structured logging.

**Generative-UI cards** are a **frontend** concern — CopilotKit renders cards
from streamed tool-call args/results + graph state. The backend's only job is to
stream those faithfully, which the AG-UI endpoint already does. No extra backend
work; the mock's "routing plan strip / ticket card / code card" are React
components keyed off real tool/subagent events.

**Telemetry footer** (tokens/tools/latency) rides the same `STATE_DELTA` from
`activity_projection` — already implemented.

**Projection is best-effort:** a failure inside `RailAGUIAgent`/`observe`/
`snapshot` must drop the rail delta, never kill the token stream. Wrap the
projection hooks accordingly.

## 5. Resource plane (C, E, F + MCP listing)

`build_resource_router(meta, thread_store, prefs_store) -> APIRouter` mounts four
routers and imports nothing from CopilotKit/AG-UI.

### 5.1 Threads (`/threads`) — the only stateful, per-user surface

Backed by `ThreadStore`. Holds **metadata only** — never message content.

| Endpoint | Purpose |
|---|---|
| `GET /threads?user_id&q=` | List `{id, title, group, updated_at}`. `group` ("Today"/"Earlier") derived from `updated_at`; optional `q` server-side title filter (UI also filters live). |
| `POST /threads` | Create empty thread → `{id}`. Frontend uses this id as the AG-UI run's `thread_id`. |
| `PATCH /threads/{id}` | Set title (rename). |
| `DELETE /threads/{id}` | Remove metadata row **and** clear checkpointer state for that `thread_id`. |

**Auto-titling:** default `"New chat"`; the frontend PATCHes a truncated first
user message as the title. Frontend-driven to avoid coupling the stream to the
thread store. LLM-generated titles are explicitly out of scope.

```python
class ThreadRecord(TypedDict):
    id: str; user_id: str; title: str; created_at: datetime; updated_at: datetime

class ThreadStore(Protocol):
    async def list(self, user_id: str, q: str | None = None) -> list[ThreadRecord]: ...
    async def create(self, user_id: str, title: str = "New chat") -> ThreadRecord: ...
    async def rename(self, thread_id: str, title: str) -> None: ...
    async def delete(self, thread_id: str) -> None: ...
    async def touch(self, thread_id: str) -> None:  # bump updated_at on run complete
        ...
```

### 5.2 Threads ↔ chat content: two stores, one key

```
ama_threads (ThreadStore)          LangGraph checkpointer (existing Postgres saver)
─────────────────────────          ────────────────────────────────────────────────
id (= thread_id)  ◄── same key ──►  config {"configurable": {"thread_id": id}}
user_id                             → messages[], files, todos, deep-agent state
title                               (the actual conversation content)
created_at / updated_at
```

- `ThreadStore` = the **index** (left rail).
- The **checkpointer** = the **content** (already resumable today; we add nothing).

**Switching a conversation:** frontend runs the AG-UI agent with the selected
`thread_id`; CopilotKit's LangGraph integration loads that thread's state from
the checkpointer and rehydrates the center pane.
**Verification point:** if CopilotKit's built-in rehydration is insufficient, add
a thin read-only `GET /threads/{id}/messages` calling
`graph.aget_state({"configurable": {"thread_id": id}})`.

**Lifecycle:** `POST` mints a new UUID `id` + metadata row (no checkpoint until
the first streamed message writes it); `DELETE` removes both metadata and
checkpoint; `touch()` on run-completion keeps ordering/grouping accurate (the one
write-back from the streaming plane into `ThreadStore`).

### 5.3 Skills (`/skills`)

- `GET /skills` lists what the agent actually loaded, via **deepagents' own
  loader** — `deepagents.middleware.skills._alist_skills(backend, source_path)`
  over `meta.skills_map` sources + the resolved backend, deduped last-wins.
  Wrapped in our `discover_skills(meta, backend)` helper so a future public-API
  swap is one line. Returns `{name, description, category, enabled}` (`category`
  from `SkillMetadata.metadata`/source label; optional). `enabled` merged from
  `PrefsStore` (default on).
- `PATCH /skills/{name}` sets the enabled pref — **UI preference only; does not
  gate the agent this cycle.**

> This calls the loader **live**, NOT `skills_metadata` off checkpoint state,
> so it sidesteps the durable-checkpoint staleness. (The previous
> `SessionRefreshSkillsMiddleware` fix for that staleness was **rolled back on
> 2026-07-05 and no longer exists** — do not reference it.)

### 5.4 Tools (`/tools`)

- `GET /tools` enumerates MCP tools from `meta.mcp_servers_config` via
  `load_mcp_tools`, grouped by server:
  `{server, tools: [{name, description, params, access}]}`.
- `access` = READ/WRITE heuristic (write-verb tool names, or MCP tool
  annotations when present; default READ).
- **Degrades gracefully:** an unreachable/unauthed server returns with an empty
  tool list + `warnings[]`, never a 500.

### 5.5 MCP servers (`/mcp-servers`)

- `GET /mcp-servers` lists configured servers from
  `meta.mcp_servers_config.keys()` as `{name, abbr, connected, tool_count}`.
- `connected` is a **display-only** pref (real OAuth connect = deferred D).
- Optional `PATCH /mcp-servers/{name}` flips only that display flag — **no auth
  handshake**, documented as such.

### 5.6 PrefsStore

One narrow per-user KV, backed by an `ama_user_prefs` table:

```python
class PrefsStore(Protocol):
    async def get(self, user_id: str, namespace: str) -> dict[str, bool]:  # "skills" | "mcp"
        ...
    async def set(self, user_id: str, namespace: str, key: str, value: bool) -> None: ...
```

Both Protocols live in `dynagent/api/thread_store.py`; mer implements them over
Postgres in `domains/ama/web/thread_store_pg.py`.

## 6. Identity & error handling

**Identity.** Every resource endpoint and thread is scoped to a `user_id`. A
single `resolve_user_id(request) -> str` FastAPI dependency in
`domains/ama/web/app.py` resolves it layered: (1) a trusted header
(`X-User-Id`) / verified session-JWT if present; (2) dev fallback to a
`DEFAULT_USER_ID` env for local runs. The React app / CopilotKit passes the
identity so AG-UI runs and REST calls share the same `user_id` (threads created
in chat appear in the list). GitHub OAuth remains a **later drop-in** at the same
seam Chainlit uses — **auth hardening deferred; identity seam in place.**

**Error handling.**
- Resource routers return typed JSON errors: `404` unknown thread, `403`
  cross-user thread access, `422` validation. Store-layer domain errors map to
  HTTP via a small exception handler.
- Skills/tools/mcp introspection **degrades, never 500s**: a backend/MCP fetch
  failure returns an empty-but-valid payload + `warnings[]` (mirrors deepagents'
  `_..._with_errors` pattern), so the left rail renders instead of breaking.
- Streaming projection is best-effort (§4): a rail error drops the delta; the
  token stream survives.

## 7. Testing

The Protocol boundary makes most of this testable without Postgres or an LLM.

- **Pure units (shared-lib):** extend `activity_projection`/`project_events`
  with synthetic AG-UI event sequences; `discover_skills` mapping + last-wins
  dedupe + `warnings[]` on error; tools READ/WRITE heuristic; thread
  Today/Earlier grouping (table-driven).
- **Resource routers (shared-lib):** FastAPI `TestClient` against **dict-backed
  fakes** implementing `ThreadStore`/`PrefsStore`. Cover threads CRUD, skills
  list merged with prefs, tools grouping + degrade path, mcp-servers list, and
  404/403/422 mappings. No DB, no model calls. Fakes live in shared-lib tests so
  the framework is testable standalone.
- **`create_agui_app` composition (shared-lib):** smoke test with a **stub agent
  factory** (no LLM) asserting `/agent` + all resource routes + `/health` mount.
- **Postgres impls (mer):** `thread_store_pg` + prefs marked `integration`,
  following mer's `common/db` patterns (ephemeral Postgres). Only these need a DB.

New tests must pass on their own; keep them isolated from shared-lib's ~43
known-pre-existing unit failures rather than folding into those modules.

## 8. Out of scope / deferred

- Real MCP connect / OAuth handshake (D).
- Skill/MCP toggles gating actual agent behavior (introspection-only this cycle).
- Retiring the Chainlit AMA server.
- A second (non-AG-UI) chat transport for non-UI clients.
- LLM-generated conversation titles.
- GitHub OAuth on the FastAPI app (identity seam in place; hardening later).

## 9. Open verification points (resolve during implementation)

1. CopilotKit LangGraph rehydration of prior thread messages on `thread_id`
   switch — else add `GET /threads/{id}/messages`.
2. Exact public/stable entry point for deepagents skill discovery
   (currently `_alist_skills`, underscore-private) — isolated behind
   `discover_skills`.
3. MCP tool `access` (READ/WRITE) source — annotations vs. name heuristic.
