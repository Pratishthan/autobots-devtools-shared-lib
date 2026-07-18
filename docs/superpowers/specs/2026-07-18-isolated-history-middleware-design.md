# Isolated History via Middleware — Design

**Date:** 2026-07-18
**Status:** Approved (supersedes the archives-in-state design behind ADR 0001 and the plan
`docs/superpowers/plans/2026-07-17-isolated-history-mode.md`)

## Goal

Per-agent message history in the classic Dynagent engine: on handoff the arriving agent starts
fresh with a summary briefing of the departing agent's work, and a revisited agent gets its own
rolling summary back. Achieved with **one self-contained middleware** instead of handoff-tool
surgery, archives, and YAML config.

## Requirements (agreed)

Must-have:

1. **Fresh context on handoff** — the arriving agent gets a compact briefing, not the full shared
   history.
2. **Revisit memory** — a revisited agent gets its own rolling summary back.

Explicitly dropped (not requirements):

- Full user-facing transcript reassembly (`reassemble_transcript`). The existing
  `SummarizationMiddleware` already makes `state["messages"]` lossy after compaction; this design
  accepts the same class of behavior.
- Raw history retrieval (`get_my_history` tool, per-agent archives).
- Per-agent `handoff_payload` flags (`summary`/`full`/`none`) and per-agent `summary_prompt` YAML
  keys.
- `history_mode` YAML config — opt-in moves to the `create_base_agent` call site.

## Architecture

One new module: `src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py`.

```python
class IsolatedHistoryState(AgentState):
    agent_summaries: NotRequired[dict[str, BaseMessage]]
    context_agent: NotRequired[str]


class IsolatedHistoryMiddleware(AgentMiddleware):
    state_schema = IsolatedHistoryState

    def __init__(
        self,
        model: BaseChatModel,
        *,
        summary_prompt: str = DEFAULT_HANDOFF_SUMMARY_PROMPT,
        trim_tokens_to_summarize: int | None = 4000,
    ) -> None: ...
```

Key decisions:

- **Standalone, public API only.** Subclasses `AgentMiddleware` directly — *not*
  `SummarizationMiddleware` — so no private-method coupling. The summarize step is a small local
  helper built on public API: `model.invoke`/`ainvoke`, `get_buffer_string`, `trim_messages`,
  `count_tokens_approximately`. Both `before_model` and `abefore_model` are implemented so the
  middleware works in sync (batch) and async engines.
- **Call-site opt-in, zero shared-lib wiring.** `create_base_agent` already accepts a
  `middleware` sequence; a use case (e.g. Designer in `autobots-agents-mer`) opts in with
  `create_base_agent(middleware=[IsolatedHistoryMiddleware(model=lm())])`. No changes to
  `base_agent.py`, `agent_config_utils.py`, `AgentMeta`, or the `handoff` tool. This is
  consistent with other engine-composition concerns (`checkpointer`, `sync_mode`) that already
  live at the call site rather than in `agents.yaml`.
- **State extension via middleware `state_schema`.** `create_agent` merges every middleware's
  `state_schema` into the resolved agent schema (verified in the installed langchain,
  `agents/factory.py`; the factory docstring recommends exactly this pattern). `Dynagent` in
  `models/state.py` is untouched; the two keys exist only when the middleware is installed.
- **`agent_summaries` maps agent name → `BaseMessage`.** The stored value is the summarizer's
  returned `AIMessage` as-is: `.text` is the summary, and provenance (model name, usage
  metadata, response id) rides along for observability. langgraph's serializer handles
  `BaseMessage` in any state channel, so this is checkpointer-safe (InMemorySaver and
  AsyncPostgresSaver alike). Briefing messages are constructed fresh from `.text` at swap time —
  the stored message itself is never inserted into `messages` (prefixes differ by context, and
  re-inserting the same message id across wipes invites `add_messages` id collisions).

## Detection (no handoff-tool changes)

The `handoff` tool keeps its legacy behavior: it writes `agent_name` via `transition_cmd`. The
middleware detects the change in `before_model`/`abefore_model`:

- `state["agent_name"]` absent → return `None` (nothing to track yet).
- `context_agent` absent → return `{"context_agent": agent_name}` (first model call).
- `context_agent == agent_name` → return `None`. Self-handoff is therefore a natural no-op.
- Otherwise → perform the swap below.

Because the swap runs in `before_model` — after all ToolMessages of the previous AI turn have
landed — the old plan's "handoff must be the only tool call in its AI turn" limitation does not
exist here.

## The swap

With `departing = context_agent` and `arriving = agent_name`:

1. **Eager roll-forward summary.** Render the live slice (`trim_messages` to the configured
   budget, then `get_buffer_string`). If `agent_summaries[departing]` exists, prepend its `.text`
   as a "Previous summary of your earlier work" block so the summary rolls forward. One LLM call
   produces the new summary; store the returned `AIMessage` in `agent_summaries[departing]`.
2. **Fresh context for the arriving agent**, in order:
   - `RemoveMessage(id=REMOVE_ALL_MESSAGES)` — full wipe.
   - Resume briefing (only if `agent_summaries[arriving]` exists — this is the revisit memory):
     `HumanMessage("[Resuming as {arriving}] Summary of your previous work:\n{text}")`.
   - Handoff briefing (always): `HumanMessage("[Handoff from {departing}]\n{text}")`.
   - Carried in-flight user message (if one exists): a fresh copy of the latest `HumanMessage`
     that is not a briefing.
3. **Return the update** — new containers, never mutating input state:
   `{"messages": fresh, "agent_summaries": {...}, "context_agent": arriving}`.

Synthetic messages are marked in `additional_kwargs[HANDOFF_MARKER]` (`HANDOFF_MARKER =
"dynagent_handoff"`) with value `"briefing"` (resume/handoff briefings — never eligible to be
carried) or `"carried"` (the carried copy — eligible to be carried again on the next hop).
`find_inflight_user_message` (module-level, pure) returns the latest `HumanMessage` whose marker
is not `"briefing"`.

## Middleware ordering

Recommended stack (as composed by `create_base_agent`):
`[inject_agent, SummarizationMiddleware, IsolatedHistoryMiddleware]` — caller middleware is
appended after the built-ins. Accepted caveat: on the rare turn where a handoff coincides with
the token-threshold trigger, `SummarizationMiddleware` compacts first and the wipe then discards
that work — one wasted LLM call, no correctness issue. After a wipe the compactor sees a tiny
message list and no-ops; it still protects long single-agent visits, and if it compacts
mid-visit, the rolled summary simply folds the compacted content.

## Error handling

The summarize helper never raises: on LLM failure it returns an explanatory placeholder string
(matching `SummarizationMiddleware`'s judgment call — handoff continuity over summary fidelity).
The wipe still happens, the in-flight user message still carries, and the briefing carries the
placeholder text.

## Public surface

- `IsolatedHistoryMiddleware` exported from `autobots_devtools_shared_lib.dynagent` (added to
  `__all__`).
- Module constants `HANDOFF_MARKER` and `DEFAULT_HANDOFF_SUMMARY_PROMPT` importable from the
  module for tests and prompt customization.

## Testing

`tests/unit/test_history_middleware.py` (new), with the summarize step stubbed (fake model or
patched helper — no real LLM):

- First model call sets `context_agent`; same-agent call is a no-op (`None`).
- Missing `agent_name` is a no-op.
- Swap: wipe verified through the real `add_messages` reducer (old message ids gone); handoff
  briefing present; in-flight user message carried for every path; briefings never re-carried.
- Revisit: resume briefing appears with the stored summary text; prior summary folds forward
  into the summarizer input.
- `agent_summaries` stores the summarizer's `AIMessage`; input state containers are not mutated.
- Composition smoke test: `create_agent`/`create_base_agent` with the middleware merges
  `IsolatedHistoryState` (the custom keys round-trip through a graph step with a fake model).
- All existing tests pass untouched (nothing in the shared path changes).

## Documentation

- New `docs/adr/0002-isolated-history-via-middleware.md`; mark ADR 0001 as
  `superseded by 0002` (archives-in-state, payload flags, and payload-only-spine-via-handoff
  decisions are dead).
- `docs/features/isolated-history.md`: usage (call-site opt-in snippet), semantics table,
  ordering caveat, and what `state["messages"]` now means.
- Mark the old plan `docs/superpowers/plans/2026-07-17-isolated-history-mode.md` as superseded
  by the plan produced from this spec.

## Future extensions (explicitly not now)

- Domain-tuned `summary_prompt` per use case — already supported via the constructor parameter.
- Per-agent payload behavior, raw archives, transcript reassembly — only if a concrete need
  appears; ADR 0001's machinery documents how they would work.
