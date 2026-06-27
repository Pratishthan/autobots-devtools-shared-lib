# Custom React UI Integration for Dynagent (CopilotKit / AG-UI)

**Date:** 2026-06-22
**Status:** Design — pending user review
**Repo:** autobots-devtools-shared-lib

## Problem

Dynagent agents are currently served to a UI via **Chainlit** (`dynagent/ui/default_ui.py` +
`dynagent/ui/ui_utils.py`). We want to drive a **custom React UI** instead, using an
**existing framework** rather than building a chat protocol from scratch. The `ui/Atlas Chat.html`
mockup (plus `app.jsx`, `ui.jsx`, `styles.css`) is a **disposable** visual reference only — it is
not part of the integration and will not be wired into the build.

## Goals

- Stream a Dynagent LangGraph agent into a React chat UI with **streaming-chat parity** to the
  current Chainlit experience: token streaming, tool-call visibility, and structured-output
  rendering.
- Reuse an off-the-shelf framework (CopilotKit / AG-UI) instead of hand-rolling transport.
- Keep the integration **generic and reusable** in shared-lib, mirroring how `default_ui.py`
  is a drop-in entry point for any domain.
- Leave the existing graph, tools, config, and tracing untouched.

## Non-Goals (v1)

- File uploads (the existing `_upload_file_to_server` flow) — deferred.
- CopilotKit generative UI / shared agent state / human-in-the-loop — deferred.
- Atlas visual reskin — deferred to a later phase; v1 uses CopilotKit's prebuilt UI.
- Persistent checkpointer / thread storage — v1 uses `InMemorySaver`, matching `invoke_agent`.
- Contract tests, frontend tests, and E2E — deferred (see Testing).

## Decisions (locked during brainstorming)

| Topic | Decision |
|-------|----------|
| UI framework | CopilotKit, built on the AG-UI protocol |
| React build tooling | Next.js (App Router) |
| Python ↔ React transport | FastAPI + CopilotKit Python SDK (self-hosted), **not** langgraph-cli |
| Chat UI | Prebuilt `@copilotkit/react-ui` first; reskin to Atlas later |
| v1 feature scope | Streaming chat parity (tokens + tool calls + structured output) |
| Placement / reuse | Generic in shared-lib, mirroring `default_ui.py`; reference Next.js app also in shared-lib |

## Architecture

Three independently understandable layers:

```
Browser (Next.js + CopilotKit React)
   |  CopilotKit wire protocol
   v
Next.js API route  /api/copilotkit       <- CopilotRuntime proxy (keeps keys server-side)
   |  AG-UI protocol (HTTP/SSE)
   v
FastAPI AG-UI endpoint  (shared-lib)      <- LangGraphAGUIAgent wraps create_base_agent()
   |  astream_events (v2)
   v
LangGraph CompiledStateGraph  (existing Dynagent)
```

The only new code is the **FastAPI AG-UI server** (small, generic) and the **Next.js reference
app**. The graph, tools, config, and tracing are reused as-is. The Next.js runtime is a thin proxy
— no agent logic lives there; it also keeps any provider keys server-side (the browser never talks
to FastAPI directly).

Validated against current (June 2026) CopilotKit docs and the official `CopilotKit/with-langgraph-fastapi`
starter. Relevant package surface:

- **Python:** `copilotkit` / `ag-ui-langgraph` — `LangGraphAGUIAgent` wraps a compiled LangGraph
  graph; `add_fastapi_endpoint` registers it on a FastAPI app.
- **Next.js:** `@copilotkit/runtime` — `CopilotRuntime` + `LangGraphHttpAgent` (points at the
  FastAPI deployment) + `ExperimentalEmptyAdapter` (the agent does its own LLM calls), exposed via
  `copilotRuntimeNextJSAppRouterEndpoint`.
- **React:** `@copilotkit/react-core` + `@copilotkit/react-ui` — `<CopilotKit runtimeUrl=... agent=...>`
  wrapping `<CopilotChat>`.

## Components & Placement

### New: `dynagent/ui/copilotkit_server.py` (shared-lib, generic)

A reusable FastAPI app factory parallel to `default_ui.py`:

- `create_copilotkit_app(agent_name: str = "coordinator") -> FastAPI`
- Builds the graph via `create_base_agent()` (with an `InMemorySaver` checkpointer), wraps it in
  `LangGraphAGUIAgent`, and registers it with `add_fastapi_endpoint`.
- Consuming domains set `DYNAGENT_CONFIG_ROOT_DIR` (per existing convention) and call the factory —
  the same drop-in contract as Chainlit today.
- Reuses existing Langfuse/OTel wiring: the Langfuse callback is injected into the graph run config
  the same way `stream_agent_events` / `invoke_agent` already do.

### New: `ui/` Next.js reference app (shared-lib)

- `app/api/copilotkit/route.ts` — `CopilotRuntime` with a `LangGraphHttpAgent` pointing at the
  FastAPI endpoint, `ExperimentalEmptyAdapter`, exposed via `copilotRuntimeNextJSAppRouterEndpoint`.
- A page rendering `<CopilotKit runtimeUrl="/api/copilotkit" agent="coordinator">` around
  `<CopilotChat>` from `@copilotkit/react-ui`.
- Fresh Next.js `package.json` under `ui/`.

### Dependencies

- **Python:** add `copilotkit` / `ag-ui-langgraph` as an optional dependency group (like Chainlit),
  so invoke/batch-only consumers don't pull it.
- **JS:** new Next.js project under `ui/`.

### Disposable

`ui/Atlas Chat.html`, `app.jsx`, `ui.jsx`, `styles.css` are kept only as a styling reference for a
future reskin and are not part of the build.

## Data Flow (one message)

1. User types in `<CopilotChat>`; CopilotKit POSTs to `/api/copilotkit`.
2. The Next.js `CopilotRuntime` forwards over AG-UI to the FastAPI endpoint, carrying a `thread_id`
   (CopilotKit manages thread identity; it maps to the LangGraph checkpointer/session).
3. `LangGraphAGUIAgent` runs the graph and translates `astream_events` into AG-UI events:
   token deltas -> streamed assistant text; `on_tool_start`/`on_tool_end` -> tool-call events;
   `structured_response` -> a final structured message.
4. Events stream back through the Next.js proxy to the browser and render incrementally.

This is the same event taxonomy `ui_utils.py` already handles for Chainlit, re-targeted to AG-UI.

## Error Handling, State, Observability

- **Sessions/threads:** CopilotKit's `thread_id` becomes the LangGraph `thread_id`; v1 uses
  `InMemorySaver` (matching `invoke_agent`'s default). Persistent checkpointer is future work.
- **Tracing:** existing Langfuse/OTel wrapping is preserved by injecting the Langfuse callback into
  the run config, as the current streaming/invoke paths do.
- **Failure modes:** FastAPI unreachable -> the Next.js route returns a clean error surfaced in chat;
  agent exception -> caught and rendered as an assistant error message, not a blank stream.
- **Security/CORS:** the browser never calls FastAPI directly — only the Next.js proxy does, keeping
  any provider keys server-side.

## Testing (reduced scope for v1)

- **One Python smoke test:** `create_copilotkit_app()` builds and mounts without error; a FastAPI
  `TestClient` confirms the AG-UI route is registered.
- **Manual verification** of the chat flow: run FastAPI + Next.js, send a message, confirm
  streaming, tool-call visibility, and structured-output rendering.
- **Deferred:** contract tests (AG-UI event parity vs Chainlit), frontend unit tests, and E2E
  (Playwright). Noted as future work, not built in v1.

## Future Work

- Reskin the prebuilt CopilotKit UI to the Atlas design (headless hooks: `useCopilotChat` /
  `useCoAgent`).
- File uploads wired to the existing file server.
- CopilotKit generative UI / shared agent state / human-in-the-loop.
- Persistent checkpointer and thread storage.
- Contract + frontend + E2E test coverage.

## Open Questions

- Which domain/agent to use as the reference target for manual verification (default: `coordinator`,
  as in `default_ui.py`).
- Deployment story for the Next.js app alongside the existing FastAPI servers (out of scope for this
  design; revisit at implementation).
