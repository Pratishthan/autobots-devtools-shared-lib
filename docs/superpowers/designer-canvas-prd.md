# PRD — Designer Canvas: An Agentic LLD Authoring Environment

**Status:** Draft — decisions captured from design debate
**Author:** Doc PK + Claude
**Context:** Dynagent framework · MER domain · Designer
**Supersedes:** Chainlit as the Designer front end (for the Designer domain specifically)

-----

## 1. Summary

Designer today uses Chainlit, a chat-first UI. Designer is not a chat app — it is a **staged authoring pipeline that produces one structured artifact** (the LLD). This PRD proposes replacing the Chainlit shell for Designer with a purpose-built **canvas authoring environment**: the LLD is the permanent centerpiece, agents are collaborators that fill it in, and conversation is demoted to a contextual sidebar.

The mental model is **Cursor / Linear, not ChatGPT** — agents operating inside a structured artifact, not voices in a transcript.

-----

## 2. Problem Statement

Chainlit’s core metaphor is a linear message scroll. For LLD authoring this is an impedance mismatch:

- The **deliverable gets buried in the transcript** instead of being the surface the user navigates.
- **Multi-agent pipeline state is invisible** — which agent is working, which sections are pending/complete is hidden in sequential messages and CoT steps.
- **Approval gates and spec-drift review** — central to the workflow — have no natural home; every correction routes back through the prompt box.
- **Brownfield scope confirmation** (“this touches X LPUs, Y models”) wants an interactive impact panel, not a paragraph the user scrolls past.

The deciding question was not “which framework” but **“is the interaction model document-centric or chat-centric?”** For LLD authoring the answer is clearly document-centric.

### Why not just customize Chainlit

Chainlit (2.9.6) supports restyling (config.toml, custom_css/js, CustomElement, custom_build fork). That covers **owning the look**. It does **not** cover **owning the interaction model** — Chainlit’s frame is a chat-first shell with a pinned composer, and the desired IA (document canvas primary, chat demoted, outline navigator, impact panel, diff view, validation board, stage rail) is a different information architecture the frame resists. The design team’s ambition is “rethink how a person authors an LLD with agents,” which is the case where Chainlit becomes the thing you perpetually work around.

-----

## 3. Core Concept

The LLD is the center of the screen, permanently. Its template sections — models, behaviours, services, test data, validation, §11 scenarios — are the scaffolding, and they map close to one-to-one onto the agent topology. **The document outline *is* the pipeline view**: empty sections waiting, a section with its agent actively working, a section complete and awaiting sign-off. The stage rail is the coordinator’s routing made visible. Conversation becomes contextual — the user talks to an agent *next to* the section it owns.

### The key realization

Designer outputs are **schema-validated JSON** (`model.json`, `behaviour.json`, `service.json`, …). The LLD is therefore **not a text document** — it is a structured object graph that *renders as* a document.

This is the single most important framing: we are **not** building a freeform collaborative text editor (cursors, conflict resolution, undo rabbit hole). We are building a **read-only renderer over structured state**, with chat as the only input. The canvas is a pure function: `render(lld_state) → view`. State is server-authoritative; the frontend never mutates, it subscribes and re-renders.

-----

## 4. Decisions (locked)

|#  |Decision                                                                                            |Rationale                                                                                                                                                                                                                                                                                                              |
|---|----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|D1 |**Replace Chainlit with a custom canvas environment for Designer**                                  |Interaction model is document-centric; Chainlit’s chat frame resists the required IA.                                                                                                                                                                                                                                  |
|D2 |**Canvas is read-only; chat (sidebar) is the only input**                                           |Eliminates contenteditable, cursors, CRDT/OT, keystroke autosave, diff-on-edit. Collapses the hardest problems out of existence.                                                                                                                                                                                       |
|D3 |**Click-to-reference (selectable, not editable) sections**                                          |Chat-only input removes the user’s ability to *point*. Clicking a section pins it as the chat’s context target — an @-mention of structure — so the agent gets an unambiguous “operate on *this*.”                                                                                                                     |
|D4 |**Sections rendered as Markdown via Dynadoc (Jinja templates)**                                     |Reuses existing JSON→Markdown capability (feature branch `Dynadoc`); canvas reads as the final artifact will; same projection Nurture consumes.                                                                                                                                                                        |
|D5 |**Node identity lives in the canonical JSON, not minted at render time**                            |One identity serves three masters: canvas click resolution, brownfield `Modify` targeting, and KG cross-artifact edges (LLD ↔ Java ↔ Gherkin ↔ Jira).                                                                                                                                                                  |
|D6 |**Identity = the node’s own natural key; parentage is a relationship (edge), not a substring**      |Path-encoded keys (`mer.txn.behaviour.x`) assume a fixed authoring path designers don’t follow, and break on re-parent. Containment is an edge that can change without touching identity.                                                                                                                              |
|D7 |**Natural keys are globally unique for models, services, LPUs**                                     |An LPU translates to a Java class; the codebase namespace already enforces uniqueness and makes renames a deliberate refactor. Durability is *inherited* from an existing constraint, not engineered.                                                                                                                  |
|D8 |**Click-to-reference operates at entity grain only**                                                |Targets are the LPU / model / service / scenario-block / validation-block as wholes — each a globally-unique-named node. No below-grain (single rule / single scenario row) targeting. This means the flat natural key carries the entire system: no surrogate IDs, no owner+leaf pairs, no uniqueness-scope reasoning.|
|D9 |**IDs/keys are minted deterministically by the framework, never by the LLM**                        |Avoids collisions, reuse, hallucinated references. Lives in the write-path (`write_file` tool family). Consistent with “deterministic processing, LLM only where flexibility is needed.”                                                                                                                               |
|D10|**The identity field is platform-owned schema structure (parent schemas), not a consumer directive**|Identity is structural, not consumer-specific intelligence.                                                                                                                                                                                                                                                            |

-----

## 5. Architecture Implications

### 5.1 Decoupling (the bet is bounded)

Everything below the UI survives unchanged: agents, prompts, schemas, handoff, `batch_invoker`, validation gates. Dynagent already emits a stream of agent events; today Chainlit consumes it, tomorrow the canvas frontend does. **The change is bounded to the frontend + a thin event/state contract — it is not a rewrite of Designer.**

The same event-consuming shell is what Nurture and KBE plug into later, which removes the fragmentation concern of “custom UI per domain.”

### 5.2 Event contract (the real interface)

The frontend is a **reducer over Dynagent’s event stream**. The contract to name deliberately (illustrative):

- `stage_changed` — coordinator routing / pipeline progress (drives the stage rail)
- `section_started` — an agent has begun a node (drives “regenerating…” shimmer)
- `section_updated` — a node’s structured payload is complete (swap in atomically)
- `gate_changed` — a validation gate flipped (drives the live checklist panel)

### 5.3 Rendering

- **Atomic, not token-by-token.** A schema-validated object is only meaningful when complete; render a “regenerating…” shimmer and swap in the finished section. Do not stream half-valid JSON into a structured view.
- **Per-node Dynadoc invocation.** Do not render the whole LLD into one Markdown blob — that destroys node identity. Render each section as its own Markdown fragment carrying its node key (anchor / `data-node-id` / comment marker that survives into the DOM). Click reads the key off the nearest marked ancestor.
- **Dynadoc likely needs a second mode**, not a rewrite: it was built as an *export* concern (batch, whole-doc). The canvas needs *incremental, identity-preserving* rendering (re-render one section on its event, keep the key mapping intact, swap the fragment). Templates are shared; the invocation contract differs. **Open: confirm the branch can render a single section in isolation.**

### 5.4 Identity & the Knowledge Graph

- Node identity = natural key (`OverdraftCheck`, `validate-email`, …).
- Containment is a **reference graph, not a tree.** A shared LPU used across services has **multiple parents** — one node, many inbound `uses` edges. “Which services depend on this LPU?” is a one-hop query; a brownfield change to a shared LPU automatically surfaces every affected service.
- A shared LPU’s own validations/scenarios belong to **the LPU** (intrinsic to the class), not to the referencing service.

### 5.5 Regeneration contract (the one place the guarantee can leak)

Regeneration operates at **node grain**: the agent is told “you are updating `OverdraftCheck` — keep its key — return the whole node.” Inside the node it has free rein; it cannot touch siblings.

**Required guard (wire from day one):** before writing a regenerated node, the framework verifies the returned key matches the targeted key. If an agent renames `OverdraftCheck` → `OverdraftValidator` mid-regeneration, that is an orphan-plus-newborn, not an update, and silently breaks KG edges and brownfield resolution. Cheap guard, lives in the deterministic write-path.

-----

## 6. In / Out of Scope

**In scope**

- Read-only Markdown canvas as the primary surface for Designer
- Click-to-reference at entity grain (pin node → scope chat/agent to it)
- Contextual chat sidebar
- Stage rail (pipeline/routing visibility)
- Live validation-gate status board
- Brownfield impact panel (scope confirmation) and New/Modify/Remove redline view
- Event/state contract over Dynagent’s stream
- Incremental, identity-preserving Dynadoc rendering mode

**Out of scope**

- Freeform / WYSIWYG text editing of the LLD
- Collaborative multi-cursor editing, CRDT/OT, conflict resolution
- Below-entity-grain click targeting (single rule, single scenario row)
- LLM-minted identities
- Path-encoded hierarchical keys

-----

## 7. Risks & Costs (honest)

- **Plumbing previously free from Chainlit now owned by us:** streaming render, reconnection, autosave-of-view-state, accessibility, responsive/browser testing. Scope ruthlessly — single user, server-authoritative state.
- **Dynadoc second mode** may be more than a config change if the branch only supports whole-doc export.
- **Regeneration scope creep** — agents rewriting untargeted siblings — mitigated by node-grain scoping + key guard.
- **Fork temptation** — resist building below-grain targeting “just in case”; D8 says entity grain is sufficient.

-----

## 8. Recommended First Slice

Build **one section type end-to-end** as a vertical slice before the full shell:
event contract → per-node Dynadoc render with key-carrying marker → click → pin → scoped regenerate → key-guard on write.

-----

## 9. Open Questions

1. Can the `Dynadoc` branch render a **single section in isolation** (incremental mode), or only the whole document?
1. Exact event names/payloads for the Dynagent → frontend contract.
1. Frontend stack/hosting decision (e.g. React shell + FastAPI/websocket vs. another approach).
1. Whether the same shell is committed to as the future Nurture/KBE surface now, or kept Designer-only until proven.
1. Marker mechanism for node keys in rendered Markdown (anchor vs. `data-node-id` vs. comment) and how it survives Markdown → DOM.
