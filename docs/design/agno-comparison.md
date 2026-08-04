# Agno Cookbook vs shared-lib: Capability Comparison

**Date:** 2026-08-04
**shared-lib version:** 0.11.0b2
**Agno pinned commit:** `21d274d63052a229fccd6b2621ea2a7da8eb1527` (main as of 2026-08-03)
**Spec:** [design spec](../superpowers/specs/2026-08-04-agno-comparison-design.md)

## 1. Context & method

Compared: the [Agno cookbook](https://github.com/agno-agi/agno/tree/main/cookbook) at the pinned
commit above vs `autobots-devtools-shared-lib` at HEAD. Goal: (a) find capabilities Agno
demonstrates that Dynagent lacks, to prioritize the roadmap; (b) evaluate where Agno can
**supplement** Dynagent. Agno is not a replacement candidate; the LangChain/LangGraph core stays.

Method: shallow pass over every cookbook section (section README/index, drilling into examples only
where ambiguous; Agno docs/source consulted where the cookbook is marketing-thin — such rows are
marked "rated from docs" or "rated from source"). Shared-lib parity claims come from reading code
under `src/autobots_devtools_shared_lib/`, cited per row.

**Parity rubric:** `has` = equivalent exists and is used by at least one app (MER, Pay, Jarvis) ·
`partial` = exists but narrower/experimental · `missing` = nothing comparable · `n-a` = doesn't
apply to this architecture. Planned-but-unbuilt work rates `missing`/`partial` with a pointer to
its design doc.

**Verdict rubric (deep-dives):** **build** when the gap touches Dynagent's core loop (LangGraph
state, middleware, config) · **adopt** (pattern-borrow / library dep / sidecar) when cleanly
separable · **skip** when no consuming app has a driving use case.

## 2. Capability matrix

| Agno section | What Agno demonstrates | shared-lib equivalent | Rating |
|--------------|------------------------|-----------------------|--------|
| `00_quickstart` | Curated 12-file onboarding path: one runnable example per core capability (tools, structured output, storage, memory, RAG, learning, guardrails, HITL, teams, workflows), ending in a deployable `run.py` + `config.yaml` | None — shared-lib has reference docs and tests but no graded runnable example path for new developers | `missing` |
| `01_demo` | Production-style demo apps (wiki agent with git/Notion backends, code-search agent, voice/PDF ingestion) shipped with their own evals | Demo apps live in consuming repos: Jarvis app, `demo` domains in MER and Pay exercise the framework end to end | `has` |
| `02_agents` | Single-agent surface, 111 examples: structured/typed I/O, streaming, session state + checkpoint/fork/time-travel, guardrails (PII/injection), pre/post/tool hooks, multimodal (image/audio/video), reasoning models, caching, retries, fallback models | Structured output (`dynagent/services` converter + YAML `output_schema`), streaming (`dynagent/ui` `stream_agent_events`), sessions/state (`dynagent/models`, `dynagent/api` thread store), tool hooks approximated by `dynagent/middleware` + `dynagent/agents` injection middleware. No guardrails, multimodal, fallback models, or session forking | `partial` |
| `03_teams` | First-class Team object with coordinate/route/broadcast/tasks modes, nested teams, shared member state, member metrics, cancellation, background runs | Multi-agent on a single LangGraph via handoff + `get_agent_list` (`dynagent/agents`), shared session state (`dynagent/models`), isolated history mode with handoff payloads. No nested teams, broadcast mode, or per-member metrics | `partial` |
| `04_workflows` | Declarative workflow primitives: sequential steps, conditions, loops, parallel branches, CEL expressions, sequential-HITL decision trees | No workflow primitives in the framework; pipelines are built from coordinator agents + handoff (MER nurture pipeline) and fan-out via `batch_invoker` (`dynagent/agents`) | `partial` |
| `05_agent_os` | Hosted runtime: ~80 generated REST endpoints, Slack/Telegram/WhatsApp/MCP/A2A/AG-UI interfaces, scheduling, JWT/RBAC, component registry with versioning/approval, background run control | `dynagent/api` FastAPI resource plane (threads, skills, tools, MCP servers) + `dynagent/ui` AG-UI endpoint/Chainlit; consuming apps own their `server.py`. No chat-platform interfaces, scheduling, RBAC, or component registry | `partial` |
| `06_storage` | Session persistence via a `db` parameter across ~12 backends (Postgres, MySQL, SQLite, MongoDB, DynamoDB, Redis, Firestore, GCS, …), with history-to-context injection and session summarization | Session context via `common/services/context` (Postgres repository, Redis, cache-backed, in-memory) + thread persistence in `dynagent/api` thread store; deep engine has durable LangGraph checkpoints. Fewer backends, no built-in session summarization on the classic engine | `partial` |
| `07_knowledge` | Full RAG stack: 10+ vector DBs, readers (PDF/DOCX/CSV/web/YouTube/ArXiv/S3), six chunking strategies, hybrid search, rerankers (Cohere et al.), 14+ embedder providers, agentic RAG, Graph RAG | None — shared-lib has no vector store, embedder, chunker, or retriever abstractions | `missing` |
| `08_learning` | A real subsystem (`agno.learn`, verified in source): six learning stores (user profile, user memory, session context, entity memory, learned knowledge, decision log) on Postgres + PgVector, with ALWAYS/AGENTIC/PROPOSE extraction modes and agent tools (`remember_about`, `log_decision`) — rated from docs + source | None — `common/services/context` stores session facts but nothing is extracted or learned across sessions. Episodic memory is research-stage only (MER `docs/design/Memory-1-session.md`); plans don't count as parity | `missing` |
| `09_evals` | `AccuracyEval` (LLM-judge with hooks), `ReliabilityEval` (tool-call validation incl. teams), `PerformanceEval` (runtime/memory benchmarks), suite runner with tags, JSON reports, CI exit codes | `eval/` framework used by consuming apps: case loader + isolated workspaces (`eval/core`), deterministic/golden/written-file/LLM-judge assertions (`eval/assertions`), cost tracking, pytest-native runner (`eval/pytest_plugin`), Langfuse score posting (`eval/scoring`). Different emphases: shared-lib adds cost + workspace + tracing integration; Agno adds perf benchmarks and tool-call reliability evals | `has` |
| `10_reasoning` | Three patterns: reasoning-capable models (separate reasoning model from main model), a `think` tool for structured scratch thinking, and reasoning agents/teams that chain-of-thought before answering | Per-agent model profiles (`dynagent/llm` model resolution) can select reasoning-capable models, but there is no think tool or reasoning-agent primitive | `partial` |
| `11_memory` | `MemoryManager` on Postgres: user-scoped memories that persist across sessions, multi-user/multi-session isolation, agent-facing memory tools, memory optimization strategies | None — `common/services/context` is session-scoped task facts (the Context Spine), not cross-session user memory; no extraction or memory manager | `missing` |
| `12_context` | External systems wrapped as context providers with scoped sub-agents: filesystem, SQL, Slack, Google Drive/Gmail, Notion, git, web search, MCP; async resource lifecycle (`asetup`/`aclose`) | Integration happens via registered LangChain tools instead: MCP servers (`dynagent/api` resources, `dynagent/agents` deep MCP), file-server client, Jenkins and Node-RED tools (`common/tools`). No provider abstraction or scoped sub-agent routing | `partial` |
| `13_filesystem` | Agent filesystem (`agno.fs`): read/write/list tools, durable SQLite/Postgres backends, per-user namespaces, progress checkpoints, line-level dedup (`check_lines`/`append_file`), quotas | File-server sidecar (`common/servers/fileserver`) + client tools (`common/tools`) used by MER; deep engine mounts it as a filesystem backend (`dynagent/agents` fserver backend). No namespacing/quota/dedup helpers | `has` |
| `90_models` | 47 model providers, each with the same four patterns (completion, streaming, tool use, structured output) | `dynagent/llm` `lm()` supports exactly two providers (`LLMProvider`: gemini, anthropic) by design — the org is standardized, so provider breadth is not a goal | `n-a` |
| `91_tools` | `@tool` decorator, async tools, tool hooks, MCP client, and 70+ first-party tool integrations (search, cloud, SaaS, data, media) | LangChain `@tool` + `dynagent/tools` registry (`register_usecase_tools`), MCP servers (`dynagent/api` resources), in-house integrations (Jenkins, Node-RED, file-server, context in `common/tools`); the wider LangChain community tool ecosystem substitutes for Agno's first-party catalog | `has` |
| `93_components` | Database-backed component persistence: save/load agents, teams, workflows to Postgres/SQLite with per-save versioning, a registry for non-serializable parts (tools, schemas, models), auto-discovery | None — agent definitions are YAML files in git (`dynagent/config`, `agents.yaml` per domain); no DB-backed versioning or registry. Git-tracked YAML is the deliberate alternative (see section 4) | `missing` |
| `99_docs` | Internal docs tooling (two helper agents: `sorting_hat.py`, `workbench.py`) — rated from listing | Not a framework capability | `n-a` |
| `data_labeling` | LLM data-labeling workflows: classification, span labeling, typed extraction, pairwise ranking, multimodal labeling, multi-reviewer adjudication with IAA metrics, synthetic data generation, checkpointed fan-out | None — nothing comparable; `batch_invoker` (`dynagent/agents`) covers only the fan-out substrate | `missing` |
| `environments` | RL-style task environments: task sets, code/judge/tool-call scorers, difficulty calibration, async rollouts, SFT export — rated from listing | None — `eval/` evaluates agents but has no trainable-environment or dataset-export machinery | `missing` |
| `examples` | Full example apps (`metrics_desk`, `second_brain`, `team_brain`) — rated from listing | Same role as `01_demo`: Jarvis and the `demo` domains in MER/Pay are the workspace's example apps | `has` |
| `frameworks` | Interop adapters for other agent frameworks (claude-agent-sdk, DSPy, LangGraph, Antigravity) — rated from listing | Dynagent is built directly on LangChain/LangGraph; interop with LangGraph is the architecture, not an adapter | `n-a` |
| `gemini_3` | Gemini-specific feature tour: audio/video/PDF/CSV input, TTS, file search, prompt caching, knowledge, memory — rated from listing | Gemini is a first-class provider (`dynagent/llm`), but only text chat is surfaced; multimodal input and prompt caching are not exposed by the framework | `partial` |
| `integrations` | Grab-bag integrations: Parallel web research (search/extract/deep-research/monitor), SurrealDB memory, Discord bot; pointers to Mem0/Zep/LightRAG elsewhere | In-house integration set in `common/tools` + sidecars (`common/servers/noderedmanagerserver`, Jenkins tooling) — different, smaller set aimed at SDLC automation | `partial` |
| `observability` | 20 tracing-platform integrations (Langfuse, Phoenix, LangSmith, MLflow, Weave, …) for agents, teams, workflows | `common/observability`: Langfuse tracing (decorator + LangChain callback), OTel FastAPI instrumentation, trace propagation — standardized on one platform and used by all apps; platform breadth is not a goal | `has` |
| `scripts` | Cookbook infrastructure (DB launch scripts, formatters, cookbook runner) — rated from listing | Not a framework capability; workspace `Makefile` plays the equivalent role | `n-a` |

## 3. Gap deep-dives

Every `missing`/`partial` matrix row is either deep-dived below or listed here as not actionable
(no consuming app has a plausible near-term use):

- `03_teams` — nested teams/broadcast/per-member metrics: the single-graph handoff architecture is
  deliberate, and isolated history mode covers context control; Langfuse covers metrics.
- `06_storage` — backend breadth isn't needed (Postgres/Redis standardized); rolling session
  summaries are already arriving via isolated history mode.
- `12_context` — provider abstraction duplicates what registered LangChain tools + MCP already do here.
- `93_components` — DB-backed config versioning conflicts with the deliberate git-tracked-YAML
  approach (see section 4); git is the versioning.
- `data_labeling` — no app labels data or builds training sets today.
- `environments` — no app trains or fine-tunes models; `eval/` covers assessment needs.
- `gemini_3` — multimodal input/TTS/prompt-caching: no app consumes non-text input today.
- `integrations` — Agno's catalog targets consumer/SaaS breadth; the in-house set targets SDLC
  automation. Different aims, no overlap worth closing.
- `02_agents` residual sub-gaps (multimodal, fallback models, session forking/time-travel): no app
  use case; guardrails, the actionable part, is deep-dived below.

### Gap: Cross-session memory & learning (from `08_learning`, `11_memory`)

**What Agno provides:** A dedicated `agno.learn` subsystem: six typed stores (user profile, user
memory, session context, entity memory, learned knowledge, decision log) persisted to Postgres +
PgVector, three extraction modes (ALWAYS after each run, AGENTIC via agent tools like
`remember_about`/`log_decision`, PROPOSE with human confirmation), and runaway-protection limits.
`MemoryManager` covers the narrower user-memory slice of the same idea.

**Why it matters here:** MER's episodic memory research (`Memory-1-session.md`) is aiming at
exactly this: agents that improve across sessions by deriving lessons from traces. The nurture
pipeline's list-extractor agents would be first consumers.

**Verdict: adopt (pattern-borrow)**

Agno's store taxonomy and extraction-mode split are the mature version of what the episodic memory
design is groping toward — borrow them as the design vocabulary. The implementation should sit on
the existing context store (`common/services/context`) and LangGraph state rather than importing
`agno.learn`, which is coupled to Agno's own Agent runtime, DB schema, and AgentOS endpoints.

### Gap: Knowledge / RAG (from `07_knowledge`)

**What Agno provides:** A complete retrieval stack: vector-DB abstraction (10+ backends), document
readers, six chunking strategies, hybrid search, rerankers, embedder abstraction, and both basic
(context-injection) and agentic (agent-controlled search) retrieval modes.

**Why it matters here:** MER's `ama` domain is Q&A over project knowledge, and Pay's KBE produces
knowledge-base articles that something eventually has to retrieve. Neither has a retrieval layer.

**Verdict: build**

Build a thin knowledge module on LangChain's native primitives (vector stores, retrievers,
embedders), which slot directly into the existing agent loop and tool registry — adopting Agno's
stack would drag in a parallel abstraction layer over the same underlying databases. Scope it to
one vector backend and one chunking strategy until an app demands more.

### Gap: Guardrails (from `02_agents`)

**What Agno provides:** Built-in input/output guardrails — PII detection, prompt-injection
screening, spam filtering — that set typed `RunStatus` error states, plus pre/post/tool-level hook
points for custom checks.

**Why it matters here:** Jarvis (concierge, customer-support) and any externally-facing deployment
process untrusted user input with no screening today.

**Verdict: build**

Guardrails belong in Dynagent's core loop as `AgentMiddleware` (`dynagent/middleware`), where
`ToolResilienceMiddleware` already establishes the pattern — a natural pre-model/post-model
counterpart. Borrow Agno's check taxonomy (PII / injection / custom hooks) for scoping, but the
mechanism is middleware, which is engine-native and can't be imported from a non-LangGraph
framework.

### Gap: Declarative workflow primitives (from `04_workflows`)

**What Agno provides:** First-class workflow objects: sequential steps, conditions, loops,
parallel branches, CEL expressions for dynamic evaluation, and sequential human-in-the-loop
decision trees — deterministic pipelines without a coordinator LLM.

**Why it matters here:** MER's nurture pipeline is a fixed 9-agent sequence today driven by
coordinator prompts and handoffs — an LLM re-decides a deterministic ordering every run, which
costs turns and occasionally derails (see trace `93a31abf` findings).

**Verdict: build**

LangGraph is itself a graph/workflow engine; the gap is only that Dynagent's YAML surfaces no way
to declare fixed edges. Extend the config schema (a `pipeline:` section compiling to LangGraph
edges with conditions) rather than adopting a second orchestrator. This touches the core loop and
config — squarely the build case in the rubric.

### Gap: Quickstart example path (from `00_quickstart`)

**What Agno provides:** A graded 12-file onboarding sequence — one runnable file per capability
(tools → structured output → storage → memory → RAG → guardrails → HITL → teams → workflows) —
ending in a deployable app skeleton.

**Why it matters here:** New shared-lib consumers currently learn from CLAUDE.md, tests, and the
Jarvis source; there is no runnable, graded path, which raises onboarding cost for every new
domain team.

**Verdict: adopt (pattern-borrow)**

Copy the format, not the code: an `examples/` directory in shared-lib with one small runnable
script per existing capability (YAML agent, tools, structured output, context store, batch, eval),
ordered by dependency. Pure documentation work with no framework changes.

### Gap: Structured reasoning support (from `10_reasoning`)

**What Agno provides:** A `think` tool giving non-reasoning models a structured scratch space, and
a reasoning-agent pattern where a separate chain-of-thought agent solves the problem before the
main agent answers; reasoning-capable models selectable separately from the main model.

**Why it matters here:** Designer and nurture agents do multi-step extraction/generation where
intermediate reasoning quality directly drives output quality; model profiles already allow
reasoning models, but there is no think-tool equivalent for the default models.

**Verdict: adopt (pattern-borrow)**

A think tool is a ~20-line registered tool — trivially borrowed into `dynagent/tools` and opt-in
per agent via `agents.yaml`. The heavier reasoning-agent pattern needs no framework support at all
(it is a YAML roster + handoff arrangement), so nothing beyond the tool is worth building.

### Gap: Runtime service surface (from `05_agent_os`)

**What Agno provides:** AgentOS: ~80 generated REST endpoints, chat-platform interfaces (Slack,
Telegram, WhatsApp), A2A/MCP/AG-UI protocols, scheduled execution, JWT/RBAC security, and a
component registry — a batteries-included hosted runtime.

**Why it matters here:** Apps currently hand-roll their `server.py` per domain; scheduling and
chat-platform delivery could eventually serve SDLC automation (e.g., nurture runs on a schedule,
results to Slack).

**Verdict: skip**

`dynagent/api` + AG-UI already cover the surface the apps actually use, and the Design Philosophy
is non-intrusive tooling, not a hosted platform. Revisit if a concrete need lands for scheduled
runs or chat-platform delivery — at that point evaluate Agno as a **sidecar** (an AgentOS instance
fronting Dynagent services over A2A/MCP) before building anything.

## 4. Dynagent-only capabilities

Capabilities verified in shared-lib code with no counterpart anywhere in the Agno cookbook.
(Isolated history mode is deliberately absent from this list: it is design-and-glossary only —
`CONTEXT.md` — with no implementation yet, and plans don't count as parity in either direction.)

| Capability | Where | Why Agno's cookbook has no equivalent |
|-----------|-------|----------------------------------------|
| Deterministic document rendering | `dynadoc` (`render_document`, `render_tree`, manifest validation, agent tool wrapper) | Agno generates documents through LLM calls; a deterministic JSON → Markdown engine with schema-validated manifests has no cookbook counterpart |
| Git-tracked, YAML-config-first agent definitions | `dynagent/config` + the `agents.yaml` / `prompts/*.md` / `schemas/*.json` convention | Agno's answer (`93_components`) is DB-backed persistence with its own versioning; Dynagent versions agent definitions in git alongside code review |
| Two engines behind one config surface | `dynagent/agents` — `create_base_agent` (classic LangGraph) and `create_base_deepagent` (deepagents) share prompts, tool registry, and model profiles | The cookbook has one runtime; engine choice per domain without config rewrites is not a concept there |
| Evals as pytest tests with cost + trace scoring | `eval/pytest_plugin`, `eval/core` cost tracker, `eval/scoring` Langfuse posting | Agno ships its own suite runner; pytest-native collection (existing CI, markers, fixtures) plus per-eval cost snapshots posted as Langfuse scores has no counterpart |
| SDLC-automation integration set | `common/tools` Jenkins pipeline/builtin tools, `common/servers/noderedmanagerserver`, file-server sidecar shared across services | Agno's catalog targets consumer/SaaS APIs; CI-pipeline and Node-RED orchestration tooling is out of its scope |

## 5. Roadmap summary

One row per deep-dive in section 3, ordered by priority. P1 = an app needs it this quarter ·
P2 = clear future need · P3 = nice-to-have · — = skip.

| Gap | Verdict | Mode (if adopt) | Priority |
|-----|---------|-----------------|----------|
| Cross-session memory & learning | adopt | pattern-borrow | P1 — episodic memory work is active, first consumer identified (nurture list-extractors) |
| Declarative workflow primitives | build | — | P2 — nurture pipeline pays LLM turns today for a fixed sequence |
| Guardrails | build | — | P2 — externally-facing apps process unscreened input |
| Knowledge / RAG | build | — | P2 — `ama` domain and KBE output need a retrieval layer eventually |
| Quickstart example path | adopt | pattern-borrow | P3 — onboarding cost, docs-only effort |
| Structured reasoning support | adopt | pattern-borrow | P3 — cheap think-tool win for designer/nurture agents |
| Runtime service surface | skip | — | — revisit on a concrete scheduling/chat-delivery need; evaluate sidecar first |

## Appendix A: shared-lib module inventory

One row per subpackage under `src/autobots_devtools_shared_lib/`. Matrix rows in section 2 cite
these paths.

| Module | Capability (one line) | Key entry points |
|--------|----------------------|------------------|
| `dynagent/agents` | Agent construction and invocation for two engines — classic LangGraph agents from YAML config and deepagents-based "deep" agents — plus batch invocation, per-agent prompt/tool injection middleware, file-server-backed deep filesystem, and rubric grading | `create_base_agent`, `create_base_deepagent`, `invoke_agent`/`ainvoke_agent`, `batch_invoker` |
| `dynagent/config` | Runtime settings and provider selection (YAML config root, env-driven) | `DynagentSettings`, `LLMProvider`, `get_dynagent_settings` |
| `dynagent/llm` | Chat-model construction and per-agent model resolution (profile name / inline `provider:name` / bare name) | `lm`, `model_resolution.resolve_model_ref` |
| `dynagent/middleware` | Shared `AgentMiddleware` implementations; currently tool-execution resilience for the deep engine | `ToolResilienceMiddleware` |
| `dynagent/models` | Agent state schemas: routing keys, session id, optional user identity; deep-engine state | `Dynagent`, `DynaDeepAgent` |
| `dynagent/tools` | Use-case tool registry and state-access tools | `register_usecase_tools`, `get_all_tools` |
| `dynagent/api` | Client-agnostic FastAPI resource plane for the UI backend: threads, skills discovery, tools, MCP servers; store protocols | `router`, `thread_store`, `skills_discovery` |
| `dynagent/ui` | Streaming and UI helpers: AG-UI app/endpoint, Chainlit entry point, event streaming, approval gate with diff proposals, activity projection | `stream_agent_events`, `agui_app`, `ask_approval`/`propose_change` |
| `dynagent/services` | Structured-output conversion service | `structured_converter` |
| `dynagent/utils` | Schema directive resolution for output schemas | `schema_directive_resolver` |
| `eval/core` | Eval runner: case loading, isolated workspaces, cost tracking | `runner`, `load_eval_cases`, `workspace`, `cost_tracker` |
| `eval/assertions` | Assertion library: deterministic checks, golden files, written-file checks, LLM-as-judge; extensible registry | `register_assertion`, `llm_judge`, `golden` |
| `eval/models` | Eval data model: cases, per-turn results, assertion results, cost snapshots | `EvalCase`, `EvalResult`, `TurnResult` |
| `eval/scoring` | Posts assertion results as Langfuse scores next to agent traces | `langfuse_scorer` |
| `eval/pytest_plugin` | Runs evals as pytest tests: fixtures, collection, reporting | `plugin`, `fixtures`, `reporting` |
| `dynadoc` | Deterministic JSON → Markdown document renderer with manifest validation, plus a tool wrapper for agents | `render_document`, `render_tree`, `make_render_document_tool` |
| `common/tools` | LangChain tools for the context store, file-server client, Node-RED manager client, Jenkins pipelines/builtins, and output formatting | `make_context_tools`, `fserver_client_tools`, `jenkins_pipeline_tools` |
| `common/config` | Jenkins configuration, constants, and loaders | `jenkins_config`, `jenkins_loader` |
| `common/utils` | Client/format utilities backing `common/tools` (Jenkins HTTP, file-server client, context, formatting) | `output_format_converter`, `fserver_client_utils` |
| `common/observability` | Langfuse tracing (decorator + LangChain callback), OTel FastAPI instrumentation, trace propagation, structured logging | `tracing`, `otel_fastapi`, `get_logger` |
| `common/servers/fileserver` | FastAPI file-server sidecar (workspace file I/O for agents) | `app` |
| `common/servers/noderedmanagerserver` | FastAPI sidecar managing Node-RED instances | `app` |
| `common/services/context` | Session context store with pluggable backends: Postgres repository, Redis, cache-backed composite, in-memory | `store`, `factory`, `redis_store`, `db_repository` |
