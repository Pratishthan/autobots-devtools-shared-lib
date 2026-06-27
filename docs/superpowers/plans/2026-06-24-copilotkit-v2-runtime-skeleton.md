# CopilotKit v2 Runtime + Provider Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `ui/` to real CopilotKit **v2** so a bare `CopilotChat` streams end-to-end against the FastAPI `/agent` backend, and delete the Atlas mock.

**Architecture:** Next.js App Router app. The CopilotKit **v2** provider moves to the root `layout.tsx`; the page renders a bare `CopilotChat` from `@copilotkit/react-core/v2`. The API route becomes a v2 `createCopilotEndpoint` served over Hono at a catch-all `[[...slug]]` path, registering a single `LangGraphHttpAgent` (key `default`) that points at the backend AG-UI endpoint (`AGENT_URL` + `/agent`) with an `InMemoryAgentRunner`.

**Tech Stack:** Next 16, React 19, `@copilotkit/react-core` `1.61.0`, `@copilotkit/runtime` `1.61.0`, `hono`, TypeScript.

## Global Constraints

- CopilotKit packages pinned to `1.61.0` (match the langgraph-fastapi reference).
- Minimal skeleton only — **no** Tailwind v4 / radix / recharts / shiki; **no** `openGenerativeUI`, `a2ui`, `mcpApps`, threads, tool-rendering, or suggestions (steps 3–6).
- Connector is `LangGraphHttpAgent({ url })` — **no `graphId`**. URL = `${AGENT_URL || "http://localhost:8000"}/agent`.
- Agent registered under the key `default`; the route uses `InMemoryAgentRunner` (no `COPILOTKIT_LICENSE_TOKEN` branch — that is step 4).
- All work confined to `ui/`. No backend (`copilotkit_server.py`) changes.
- `CopilotChat` is imported from `@copilotkit/react-core/v2`; `@copilotkit/react-ui` is dropped.

---

## File Structure

- `ui/package.json` — dependency bump (v2 + hono + Next 16; drop `react-ui`).
- `ui/app/api/copilotkit/[[...slug]]/route.ts` — **new**; v2 Hono endpoint. Replaces `ui/app/api/copilotkit/route.ts` (deleted).
- `ui/app/layout.tsx` — root v2 `CopilotKit` provider.
- `ui/app/page.tsx` — bare `CopilotChat`.
- `ui/.env.example` — `AGENT_URL`.
- `ui/README.md` — drop Atlas paragraph, fix run URL.
- **Deleted:** `ui/ck-components.jsx`, `ui/ck-runtime.jsx`, `ui/ck-app.jsx`, `ui/app.jsx`, `ui/ui.jsx`, `ui/tweaks-panel.jsx`, `ui/styles.css`, `ui/copilotkit.css`, `ui/Atlas × CopilotKit.html`, `ui/Atlas Chat.html`.

> **Note on "tests":** `ui/` has no JS test runner. Each task's verification is `npm run typecheck`, `npm run build`, route/grep checks, and (Task 3) a manual end-to-end stream. Treat a failing typecheck/build as a failing test.

---

### Task 1: Dependency bump to v2 + Next 16

**Files:**
- Modify: `ui/package.json`

**Interfaces:**
- Consumes: nothing.
- Produces: a resolved `node_modules` with `@copilotkit/react-core@1.61.0`, `@copilotkit/runtime@1.61.0`, `hono`, `next@16`; `@copilotkit/react-ui` removed.

- [ ] **Step 1: Edit `ui/package.json` dependencies**

Replace the `dependencies` block so it reads exactly:

```json
  "dependencies": {
    "@copilotkit/react-core": "1.61.0",
    "@copilotkit/runtime": "1.61.0",
    "hono": "^4.12.10",
    "next": "16.1.6",
    "react": "^19.2.0",
    "react-dom": "^19.2.0"
  },
```

(Removes `@copilotkit/react-ui` and `@copilotkit/react-core@^1.10.5`; CopilotChat now comes from `react-core/v2`.) Leave `scripts`, `devDependencies`, and `overrides` unchanged.

- [ ] **Step 2: Install and capture the lockfile**

Run: `cd ui && npm install`
Expected: completes without `ERESOLVE` errors; `package-lock.json` updates. If `ERESOLVE` appears, re-run with the cause shown and resolve the peer conflict (do **not** blanket `--force`).

- [ ] **Step 3: Baseline typecheck**

Run: `cd ui && npm run typecheck`
Expected: it will likely FAIL with errors in `app/page.tsx` / `route.ts` (they still use v1 imports). Record the errors — Tasks 2–3 fix them. This step only confirms the toolchain runs under the new deps.

- [ ] **Step 4: Commit**

```bash
cd ui && git add package.json package-lock.json
git commit -m "build(ui): bump CopilotKit to v2 (1.61.0) + hono + Next 16"
```

---

### Task 2: v2 runtime route (Hono `[[...slug]]`)

**Files:**
- Create: `ui/app/api/copilotkit/[[...slug]]/route.ts`
- Delete: `ui/app/api/copilotkit/route.ts`

**Interfaces:**
- Consumes: `process.env.AGENT_URL` (optional; defaults to `http://localhost:8000`).
- Produces: an HTTP endpoint at `/api/copilotkit/**` exporting `GET`/`POST`/`PATCH`/`DELETE`, registering agent key `default`.

- [ ] **Step 1: Create the v2 route**

Create `ui/app/api/copilotkit/[[...slug]]/route.ts` with exactly:

```ts
import {
  CopilotRuntime,
  createCopilotEndpoint,
  InMemoryAgentRunner,
} from "@copilotkit/runtime/v2";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { handle } from "hono/vercel";

// The dynagent graph runs under uvicorn + ag-ui-langgraph and speaks AG-UI
// directly, so we connect with LangGraphHttpAgent (URL only — no graphId).
// The server mounts the agent at /agent; AGENT_URL is the server origin.
const defaultAgent = new LangGraphHttpAgent({
  url: `${process.env.AGENT_URL || "http://localhost:8000"}/agent`,
});

const runtime = new CopilotRuntime({
  agents: { default: defaultAgent },
  runner: new InMemoryAgentRunner(),
});

const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

export const GET = handle(app);
export const POST = handle(app);
export const PATCH = handle(app);
export const DELETE = handle(app);
```

- [ ] **Step 2: Delete the v1 route**

Run: `cd ui && git rm app/api/copilotkit/route.ts`
Expected: file removed (the new `[[...slug]]/route.ts` supersedes it).

- [ ] **Step 3: Typecheck the route**

Run: `cd ui && npm run typecheck`
Expected: no errors originating in `app/api/copilotkit/[[...slug]]/route.ts`. (Errors may still remain in `layout.tsx`/`page.tsx` until Task 3.) If `@copilotkit/runtime/v2` or `/langgraph` subpaths fail to resolve, confirm `@copilotkit/runtime@1.61.0` is installed (Task 1).

- [ ] **Step 4: Commit**

```bash
cd ui && git add app/api/copilotkit
git commit -m "feat(ui): convert runtime route to v2 createCopilotEndpoint over Hono"
```

---

### Task 3: Root v2 provider + bare CopilotChat (end-to-end)

**Files:**
- Modify: `ui/app/layout.tsx`
- Modify: `ui/app/page.tsx`

**Interfaces:**
- Consumes: the `/api/copilotkit` endpoint from Task 2; agent key `default`.
- Produces: a rendered `CopilotChat` wired to the v2 provider.

- [ ] **Step 1: Move the v2 provider into the root layout**

Replace `ui/app/layout.tsx` with exactly:

```tsx
import type { ReactNode } from "react";
import "@copilotkit/react-core/v2/styles.css";
import { CopilotKit } from "@copilotkit/react-core/v2";

export const metadata = {
  title: "Dynagent CopilotKit UI",
  description: "React chat UI for Dynagent agents over AG-UI.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      {/*
        suppressHydrationWarning: browser extensions (e.g. Grammarly) inject
        attributes onto <body> before React hydrates, which would otherwise
        surface as a hydration mismatch on first load.
      */}
      <body suppressHydrationWarning>
        <CopilotKit runtimeUrl="/api/copilotkit">{children}</CopilotKit>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Strip the page to a bare chat**

Replace `ui/app/page.tsx` with exactly:

```tsx
"use client";

import { CopilotChat } from "@copilotkit/react-core/v2";

export default function Page() {
  return (
    <div style={{ height: "100vh" }}>
      <CopilotChat />
    </div>
  );
}
```

- [ ] **Step 3: Typecheck and build**

Run: `cd ui && npm run typecheck && npm run build`
Expected: both PASS with zero errors. If `CopilotChat` is not exported from `@copilotkit/react-core/v2`, check the installed package's `v2` entry and adjust the import to the v2 chat component it exports (do not fall back to `@copilotkit/react-ui`).

- [ ] **Step 4: Manual end-to-end stream**

In one terminal start the backend (from repo root, venv active, `DYNAGENT_CONFIG_ROOT_DIR` set):
`python -m autobots_devtools_shared_lib.dynagent.ui.copilotkit_server`
In another: `cd ui && AGENT_URL=http://localhost:8000 npm run dev`
Open `http://localhost:3000`, send a message.
Expected: assistant text streams **token-by-token** in `CopilotChat`. Then stop the backend and send another message — expect a **clean error surfaced in chat**, not a blank/hung stream.

- [ ] **Step 5: Commit**

```bash
cd ui && git add app/layout.tsx app/page.tsx
git commit -m "feat(ui): root v2 CopilotKit provider + bare CopilotChat"
```

---

### Task 4: Delete the Atlas mock + env/README cleanup

**Files:**
- Delete: `ui/ck-components.jsx`, `ui/ck-runtime.jsx`, `ui/ck-app.jsx`, `ui/app.jsx`, `ui/ui.jsx`, `ui/tweaks-panel.jsx`, `ui/styles.css`, `ui/copilotkit.css`, `ui/Atlas × CopilotKit.html`, `ui/Atlas Chat.html`
- Modify: `ui/.env.example`
- Modify: `ui/README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a tree where `ui/app/` imports none of the deleted files.

- [ ] **Step 1: Confirm nothing in the build imports the mock**

Run: `cd ui && grep -rEn "ck-components|ck-runtime|ck-app|app\.jsx|ui\.jsx|tweaks-panel|styles\.css|copilotkit\.css|Atlas " app/ next.config.mjs 2>/dev/null`
Expected: **no matches**. If anything matches, stop and remove the import before deleting.

- [ ] **Step 2: Delete the Atlas mock files**

```bash
cd ui && git rm ck-components.jsx ck-runtime.jsx ck-app.jsx app.jsx ui.jsx \
  tweaks-panel.jsx styles.css copilotkit.css "Atlas × CopilotKit.html" "Atlas Chat.html"
```
Expected: all ten files removed. (If any path is already absent, drop it from the command.)

- [ ] **Step 3: Update `ui/.env.example`**

Set its full contents to:

```bash
# Origin of the FastAPI AG-UI server. The runtime route appends /agent.
AGENT_URL=http://localhost:8000
```

(Removes the obsolete `LANGGRAPH_DEPLOYMENT_URL`.)

- [ ] **Step 4: Update `ui/README.md`**

- Delete the paragraph describing `Atlas Chat.html`, `app.jsx`, `ui.jsx`, and `styles.css` as "disposable styling references for a future reskin."
- Replace the run URL line (the long `http://localhost:3000/Atlas%20...` URL) with: `Open http://localhost:3000`.
- In the Terminal 2 / env section, ensure the variable referenced is `AGENT_URL=http://localhost:8000` (not `backend=`/`LANGGRAPH_DEPLOYMENT_URL`).

- [ ] **Step 5: Verify the build is still clean**

Run: `cd ui && npm run build`
Expected: PASS (the deletions are not part of the build graph).

- [ ] **Step 6: Commit**

```bash
cd ui && git add -A
git commit -m "chore(ui): delete Atlas mock; AGENT_URL env + README cleanup"
```

---

## Self-Review

**Spec coverage** (against Sub-project 2 in the design doc):
- package.json v2 + hono + Next 16, no Tailwind/radix → Task 1. ✓
- route → `createCopilotEndpoint`/Hono `[[...slug]]`, four verbs, `LangGraphHttpAgent({url})`, `default` key, `InMemoryAgentRunner`, no genUI/a2ui/mcp/license branch → Task 2. ✓
- provider at root layout, no a2ui/genUI/ThemeProvider props, `suppressHydrationWarning` → Task 3 Step 1. ✓
- bare `CopilotChat`, remove per-page provider + `agent="coordinator"` → Task 3 Step 2. ✓
- delete the 10 mock files → Task 4 Step 2. ✓
- README paragraph + run URL fix → Task 4 Step 4. ✓
- `.env.example` → `AGENT_URL` → Task 4 Step 3. ✓
- Acceptance: install/dev/typecheck/build → Tasks 1,3; end-to-end stream + clean-error-on-stop → Task 3 Step 4; nothing imports mock → Task 4 Step 1. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full file contents or exact JSON/bash. ✓

**Type consistency:** Agent key `default` used in Task 2 (`agents: { default }`) and referenced consistently; `AGENT_URL` default `http://localhost:8000` identical in route (Task 2) and `.env.example`/dev command (Tasks 3–4); `CopilotChat`/`CopilotKit` imported from `@copilotkit/react-core/v2` throughout. ✓
