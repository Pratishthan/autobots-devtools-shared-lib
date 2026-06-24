# CopilotKit v2 Alignment — Design

Date: 2026-06-24
Status: Sub-project 1 implemented · sub-project 2 detailed (implement now)
Branch: design/react-copilotkit-ui

## Context

Our CopilotKit UI (`ui/` + `src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`)
currently diverges from the upstream reference
([CopilotKit/examples/integrations/langgraph-fastapi](https://github.com/CopilotKit/CopilotKit/tree/main/examples/integrations/langgraph-fastapi))
in two material ways:

1. **The real app is a thin CopilotKit v1 wrapper.** `ui/app/` uses `@copilotkit/* ^1.10.5`
   (classic API): per-page provider, `copilotRuntimeNextJSAppRouterEndpoint` (POST only),
   `LangGraphHttpAgent`, bare `<CopilotChat>`. The reference is on the **v2 API**
   (`@copilotkit/* 1.61.0`, `react-core/v2`, `runtime/v2`): root-layout provider,
   `createCopilotEndpoint` over Hono, `LangGraphHttpAgent({url})`, plus
   threads, generative UI/A2UI, tool rendering, suggestions, MCP. Note the connector class
   (`LangGraphHttpAgent`) is **already correct** in our v1 app — only the runtime version
   (v1 → v2) and surrounding wiring differ.
2. **The polished "Atlas" UX is a fake.** `ui/ck-*.jsx`, `ui/app.jsx`, the `Atlas *.html`
   files and `ui/styles.css` hand-reimplement the CopilotKit hook surface and speak AG-UI
   directly via `fetch`/SSE. They do **not** use real CopilotKit and are not part of the build.

The backend (`copilotkit_server.py`) serves `create_base_agent()` over AG-UI using
`ag_ui_langgraph.LangGraphAgent`. The reference's `agent/main.py` serves its graph with
**copilotkit's** `LangGraphAGUIAgent` mounted via `add_langgraph_fastapi_endpoint` into a
plain FastAPI app — exactly the self-host pattern `copilotkit_server.py` uses. The graph is
built with `langchain.agents.create_agent` plus `CopilotKitMiddleware()` /
`StateStreamingMiddleware` — the same construction style our `create_base_agent` already uses.

### Reference choice: langgraph-fastapi (not langgraph-python)

The two upstream references are ~identical on the frontend and ship a byte-identical
`serve.py`; they differ in **intended runtime**. `langgraph-python` targets the LangGraph
Platform / CLI dev server (`langgraph dev` reading `langgraph.json`, backed by `langgraph-api`),
and its frontend connects with `LangGraphAgent({deploymentUrl, graphId, langsmithApiKey})`.
`langgraph-fastapi` self-hosts the graph in a FastAPI app you own (`ag-ui-langgraph[fastapi]`
only, no `langgraph.json`), and its frontend connects with `LangGraphHttpAgent({url})`.

We align to **langgraph-fastapi** because:

- **Licensing.** `langgraph dev` is dev-only; production self-hosting of LangGraph Server
  needs a LangGraph Platform **Enterprise license** — not feasible in our setup. The fastapi
  pattern is OSS-only. (The langgraph-python reference's own `serve.py` is a fallback that
  routes *around* the platform — i.e. back to this same self-host pattern.)
- **Architecture fit.** Dynagent is a library deployed per-domain; mounting its graph into a
  FastAPI app we control matches its non-intrusive philosophy and the existing
  `default_ui.py` serving. The platform wants to own the process.
- **Simpler UI tier.** `LangGraphHttpAgent` needs only a URL — no `graphId`, and no LangSmith
  credential living in the Next.js proxy.
- **Persistence is owned, not lost.** Start with `InMemorySaver`; swap a Postgres/Redis
  checkpointer later for a durable threads drawer — no license gate crossed.

## Goal

Migrate to **real CopilotKit v2**, matching the reference architecture, and **retire the
Atlas mock entirely**, adopting the reference's component patterns (restyled later).

## Target Architecture

```
Browser ──(v2 CopilotKit provider @ root layout)──► /api/copilotkit/[[...slug]]
            CopilotChat + ThreadsDrawer + canvas       (v2 createCopilotEndpoint, Hono)
            + genUI/A2UI catalog + suggestions          LangGraphHttpAgent({ url: ".../agent" })
                                                              │
                                                              ▼
                                      FastAPI: copilotkit.LangGraphAGUIAgent @ "/agent"
                                                              │
                            create_base_agent(copilotkit=True) + CopilotKitMiddleware()
                                              (+ StateStreamingMiddleware in step 5)
```

## Decomposition (approved — 6 sequenced sub-projects)

Each sub-project gets its own spec → plan → implementation cycle. The UI stays runnable
after each. Steps 3–6 may be reordered/parallelized once 1–2 land.

1. **Backend agent alignment** *(detailed below — implemented)* — emit v2-compatible events.
2. **v2 runtime + provider skeleton** *(detailed below — implement now)* — bump to `@copilotkit/*` v2 + Next 16; convert
   `route.ts` to `createCopilotEndpoint`/Hono with `[[...slug]]`; move provider to root
   `layout.tsx`; bare `CopilotChat` working end-to-end. **Retire `ck-*.jsx`, `app.jsx`,
   the Atlas HTML files, and `styles.css` here.** Point `LangGraphHttpAgent({url})` at the
   backend AG-UI endpoint via an env var (e.g. `AGENT_URL` → `.../agent`); no `graphId` to
   wire (see endpoint-coupling note below).
3. **Tool-call rendering** — adopt the reference `tool-rendering.tsx` pattern for our tools.
4. **Persistent threads drawer** — `ThreadsDrawer` + `InMemoryAgentRunner`; the in-memory
   vs. CopilotKit Intelligence (license-token) choice is deferred to this step's spec.
5. **Generative UI / A2UI** — a2ui catalog + `openGenerativeUI`; add
   `StateStreamingMiddleware(StateItem(...))` to the backend once the streamed state key is
   defined; restyled.
6. **Suggestions + MCP apps** — example-suggestions hook + MCP server wiring.

---

## Sub-project 1 — Backend agent alignment (implement now)

### Scope

Make the dynagent graph emit the events CopilotKit v2 expects, and serve it with copilotkit's
agent wrapper, **without** changing any non-UI invocation path.

### Changes

**1. `create_base_agent` gains an opt-in `copilotkit` flag**
(`src/autobots_devtools_shared_lib/dynagent/agents/base_agent.py`)

- New parameter `copilotkit: bool = False`.
- When `True`, append `copilotkit.CopilotKitMiddleware()` to the existing middleware list
  (after `inject_agent_*` and `SummarizationMiddleware`).
- When `False` (the default), behavior is byte-for-byte unchanged — batch, CLI, and all
  domains are unaffected.
- `StateStreamingMiddleware` is **not** added here; it is deferred to step 5 because it
  requires a concrete `StateItem(state_key, tool, tool_argument)` that only exists once
  generative-UI state is defined.

**2. `copilotkit_server.py` uses copilotkit's agent + derived agent name**
(`src/autobots_devtools_shared_lib/dynagent/ui/copilotkit_server.py`)

- Build the graph with `create_base_agent(checkpointer=InMemorySaver(), copilotkit=True)`.
- Replace `from ag_ui_langgraph import LangGraphAgent` with copilotkit's
  `LangGraphAGUIAgent`; keep `add_langgraph_fastapi_endpoint`.
- Derive the agent name: `graph_id = get_default_agent() or "dynagent"`. Use it as the
  `LangGraphAGUIAgent(name=graph_id, ...)` and keep mount path `/agent`.
- Keep CORS middleware and the Langfuse callback wiring exactly as today.
- **Log the derived `graph_id` and the mount path prominently** at startup. Under the
  langgraph-fastapi pattern the frontend `LangGraphHttpAgent` targets the **URL/path**, not a
  `graphId`, so the name is informational — step 2 only needs to match `.../agent`.

**3. Dependency**
(`pyproject.toml`)

- Add the `copilotkit` Python package to the existing `[copilotkit-ui]` optional extra
  (alongside `ag-ui-langgraph`). Pin a version compatible with `LangGraphAGUIAgent` +
  `CopilotKitMiddleware` as used by the reference.

### Endpoint coupling note

With the langgraph-fastapi pattern there is **no `graphId` to couple**. The v2 frontend route
(step 2) registers `LangGraphHttpAgent({ url })` under a runtime agent key (e.g. `default` /
`coordinator`) and targets the backend by **URL/path** only. The single coupling is the AG-UI
endpoint URL: the server mounts at `/agent`, and the frontend reads that URL from an env var
(e.g. `AGENT_URL`). The server-side `LangGraphAGUIAgent(name=...)` is informational and need
not match anything on the frontend. Step 1 only needs to **mount at `/agent` and log it**.

### Out of scope for sub-project 1

- Any `ui/` frontend changes (that is step 2).
- Removing the Atlas mock files (step 2).
- `StateStreamingMiddleware` / generative-UI state (step 5).
- Threads persistence, tool rendering, suggestions, MCP (steps 3–6).

### Acceptance criteria

- `create_base_agent()` with no args produces an identical middleware stack to before
  (regression-safe for batch/CLI/domains).
- `create_base_agent(copilotkit=True)` appends `CopilotKitMiddleware()` and nothing else.
- `python -m autobots_devtools_shared_lib.dynagent.ui.copilotkit_server` starts, mounts the
  copilotkit `LangGraphAGUIAgent` at `/agent`, and logs the derived `graph_id`.
- `pip install -e ".[copilotkit-ui]"` installs `copilotkit`.
- Existing tests, lint, and type-check pass.

### Risks

- `copilotkit` package version must be compatible with our `langchain.agents.create_agent`
  and LangGraph versions; pin and verify on install.
- `LangGraphAGUIAgent` API surface differs from `ag_ui_langgraph.LangGraphAgent`
  (constructor args, event emission); verify the AG-UI endpoint still streams against a
  smoke test before declaring step 1 done.

**Status: implemented** (commits `425cd58`, `b37b265`). All acceptance criteria verified:
no-arg middleware stack unchanged; `copilotkit=True` appends only `CopilotKitMiddleware()`;
server mounts at `/agent` and logs the name; `[copilotkit-ui]` installs `copilotkit`; tests,
lint, type-check pass.

---

## Sub-project 2 — v2 runtime + provider skeleton (implement now)

### Scope

Get **real CopilotKit v2** chatting end-to-end against the FastAPI `/agent` backend with a
**bare `CopilotChat`**, convert the runtime route, move the provider to the root layout, and
**delete the Atlas mock**. Nothing styled or feature-rich yet — threads, tool rendering,
generative UI, suggestions, and MCP are steps 3–6.

**Bump scope decision: minimal skeleton.** Bring in CopilotKit v2 (`1.61.0`) + `hono` + Next 16
only. Do **not** adopt Tailwind v4 / radix / recharts / shiki here — those exist in the
reference solely for the steps 3–6 components and are pulled in by the steps that use them.
The page uses default v2 styles.

### Changes

**1. `ui/package.json` — minimal v2 bump**

- `@copilotkit/react-core`, `@copilotkit/react-ui`, `@copilotkit/runtime` → `1.61.0`.
- Add `hono` (`^4.12`).
- `next` → `16.x`; keep `react` / `react-dom` 19.
- No Tailwind / radix / recharts / shiki — deferred to the steps that consume them.

**2. `ui/app/api/copilotkit/[[...slug]]/route.ts`** (moved from `route.ts`)

- Replace v1 `copilotRuntimeNextJSAppRouterEndpoint` (POST only) with v2 `createCopilotEndpoint`
  over Hono; export `GET` / `POST` / `PATCH` / `DELETE` via `hono/vercel` `handle`.
- `new LangGraphHttpAgent({ url: \`${process.env.AGENT_URL || "http://localhost:8000"}/agent\` })`,
  registered under the `default` agent key.
- `runner: new InMemoryAgentRunner()`. **No** `COPILOTKIT_LICENSE_TOKEN` / intelligence branch
  (step 4), and **no** `openGenerativeUI` / `a2ui` / `mcpApps` (steps 5–6).

**3. `ui/app/layout.tsx` — provider at root**

- Import `CopilotKit` from `@copilotkit/react-core/v2` and `@copilotkit/react-core/v2/styles.css`.
- Wrap `{children}` in `<CopilotKit runtimeUrl="/api/copilotkit">` — no a2ui / genUI /
  ThemeProvider props yet.
- `suppressHydrationWarning` on `<body>` (browser-extension hydration, per reference).

**4. `ui/app/page.tsx` — bare chat**

- `"use client"`; render `<CopilotChat />` from `@copilotkit/react-core/v2` in a full-height
  container. Remove the per-page `<CopilotKit>` wrapper and the `agent="coordinator"` prop
  (the root provider owns the runtime; the route registers the agent as `default`).

**5. Delete the Atlas mock**

- Remove `ck-components.jsx`, `ck-runtime.jsx`, `ck-app.jsx`, `app.jsx`, `ui.jsx`,
  `tweaks-panel.jsx`, `styles.css`, `copilotkit.css`, `Atlas × CopilotKit.html`,
  `Atlas Chat.html`. (Recoverable from git history if needed for the later reskin.)
- `ui/README.md`: drop the "disposable styling references" paragraph and fix the run URL (it
  points at the now-deleted Atlas HTML) to `http://localhost:3000`.

**6. Env**

- `ui/.env.example`: replace `LANGGRAPH_DEPLOYMENT_URL` with `AGENT_URL=http://localhost:8000`
  (the server mounts `/agent`; the route appends the path).

### Out of scope for sub-project 2

- Tool-call rendering (step 3).
- Threads drawer + persistence / license-token choice (step 4).
- Generative UI / A2UI + `StateStreamingMiddleware` (step 5).
- Suggestions + MCP apps (step 6).
- Any restyle / Tailwind adoption.

### Acceptance criteria

- `npm install && npm run dev` builds clean under Next 16; `npm run typecheck` passes.
- Root-layout `CopilotKit` v2 provider renders; `page.tsx` shows a bare `CopilotChat`.
- With the FastAPI server running and LLM creds set, a chat message streams assistant text
  token-by-token through the v2 route → `LangGraphHttpAgent` → `/agent`.
- Stopping the backend surfaces a clean error in chat (not a blank stream).
- The Atlas mock files are gone and nothing in `ui/app/` imports them.

### Risks

- **Next 15 → 16** is the main risk in an otherwise small diff; `next.config.mjs` and
  `tsconfig.json` may need adjustment. Treat config breakage as in-scope for this step.
- v2 route wiring (Hono `[[...slug]]`, `InMemoryAgentRunner`) differs structurally from v1;
  verify all four HTTP verbs route before declaring done.
- End-to-end streaming verification requires the backend + LLM creds running locally.
