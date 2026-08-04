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

## 3. Gap deep-dives

## 4. Dynagent-only capabilities

## 5. Roadmap summary

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
