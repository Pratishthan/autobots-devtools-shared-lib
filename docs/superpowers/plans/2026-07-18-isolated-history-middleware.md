# Isolated History via Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-agent message history in the classic Dynagent engine via one self-contained middleware: on a detected handoff it eagerly summarizes the departing agent's context, wipes `messages`, and briefs the arriving agent (restoring a revisited agent's rolling summary).

**Architecture:** A single new module `dynagent/agents/history_middleware.py` holding pure helpers plus `IsolatedHistoryMiddleware` (subclass of langchain's `AgentMiddleware`, public API only). Detection happens in `before_model`/`abefore_model` by comparing `state["agent_name"]` (written by the untouched `handoff` tool) against a new `context_agent` key declared on the middleware's own `state_schema` — `create_agent` merges middleware state schemas, so `Dynagent` is untouched. Use cases opt in at the call site: `create_base_agent(middleware=[IsolatedHistoryMiddleware(model=lm())])`. Spec: `docs/superpowers/specs/2026-07-18-isolated-history-middleware-design.md` (supersedes ADR 0001's archives-in-state design).

**Tech Stack:** Python 3.12+, langchain 1.3.11 / langgraph (shared workspace venv `../.venv`), pytest (`asyncio_mode = "auto"`), ruff, pyright.

## Global Constraints

- All work happens inside the repo `autobots-devtools-shared-lib` (its own git repo — commit from inside it, never from the workspace root; pre-commit hooks run ruff + pyright + pytest + poetry check).
- Run commands from `autobots-devtools-shared-lib/` with the shared venv: prefix with `../.venv/bin/` (e.g. `../.venv/bin/pytest`).
- Ruff line-length 100, double quotes; pyright basic mode. Enabled ruff rules include ARG, TRY, RET — the plan's code carries the required `# noqa` comments; do not remove them.
- **Do not modify**: `tools/state_tools.py` (the `handoff` tool), `agents/base_agent.py`, `agents/agent_config_utils.py`, `agents/agent_meta.py`, `models/state.py`, or any `deep_*` module. The shared path must be byte-for-byte unchanged; all existing tests must keep passing untouched.
- **Public langchain API only** — never import from or call private members of `SummarizationMiddleware`.
- Imports verified against the installed venv: `from langchain.agents.middleware import AgentMiddleware`; `from langchain.agents import AgentState`; `from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage`; `BaseMessage` is **not** in `langchain.messages` — use `from langchain_core.messages import BaseMessage`; `from langchain_core.messages.utils import count_tokens_approximately, get_buffer_string, trim_messages`; `from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages`; `from langgraph.runtime import Runtime`; `from langchain_core.language_models.fake_chat_models import GenericFakeChatModel` (tests).
- `message.text` is a **property** (NOT a method — calling it is deprecated). `RemoveMessage` is NOT part of the `AnyMessage` union — annotate mixed lists as `list[BaseMessage]`.
- Marker vocabulary (exact strings): `HANDOFF_MARKER = "dynagent_handoff"`, values `"briefing"` (never carried, engine-generated) and `"carried"` (copy of the in-flight user message, eligible for re-carrying).

## File Structure

| File | Responsibility |
|---|---|
| `src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py` (create) | Everything: marker constants, default prompt, pure helpers (`find_inflight_user_message`, `render_summary_input`, `build_swap_update`), `IsolatedHistoryState`, `IsolatedHistoryMiddleware` |
| `src/autobots_devtools_shared_lib/dynagent/__init__.py` (modify) | Export `IsolatedHistoryMiddleware` |
| `tests/unit/test_history_middleware.py` (create) | All tests for the module (helpers, swap builder, middleware, composition smoke, export) |
| `docs/adr/0002-isolated-history-via-middleware.md` (create) | Decision record |
| `docs/adr/0001-isolated-history-mode.md` (modify) | Status → superseded by 0002 |
| `docs/features/isolated-history.md` (create) | Usage documentation |
| `docs/superpowers/plans/2026-07-17-isolated-history-mode.md` (modify) | Superseded banner |

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

```bash
cd /Users/pralhad/work/src/ws-autobots/autobots-devtools-shared-lib
git checkout -b feat/isolated-history-middleware
```

---

### Task 1: Module skeleton — constants, prompt, pure helpers

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py`
- Test: `tests/unit/test_history_middleware.py` (create)

**Interfaces:**
- Consumes: nothing project-internal beyond `get_logger`.
- Produces (all in `autobots_devtools_shared_lib.dynagent.agents.history_middleware`):
  - `HANDOFF_MARKER = "dynagent_handoff"`, `BRIEFING = "briefing"`, `CARRIED = "carried"`
  - `DEFAULT_HANDOFF_SUMMARY_PROMPT: str` (contains the `{messages}` placeholder)
  - `find_inflight_user_message(messages: Sequence[AnyMessage]) -> HumanMessage | None`
  - `render_summary_input(messages: Sequence[AnyMessage], prior_summary_text: str | None, trim_tokens: int | None) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_history_middleware.py`:

```python
# ABOUTME: Unit tests for IsolatedHistoryMiddleware and its pure helpers.
# ABOUTME: No real LLM — summaries are stubbed or served by fake chat models.

from langchain.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.dynagent.agents.history_middleware import (
    BRIEFING,
    DEFAULT_HANDOFF_SUMMARY_PROMPT,
    HANDOFF_MARKER,
    find_inflight_user_message,
    render_summary_input,
)

# --- find_inflight_user_message ---


def test_inflight_finds_latest_human():
    messages = [
        HumanMessage(content="first"),
        AIMessage(content="reply"),
        HumanMessage(content="second"),
        AIMessage(content="reply 2"),
    ]
    found = find_inflight_user_message(messages)
    assert found is not None
    assert found.content == "second"


def test_inflight_skips_briefing_messages():
    messages = [
        HumanMessage(content="real question"),
        HumanMessage(
            content="[Handoff from alpha] stuff",
            additional_kwargs={HANDOFF_MARKER: BRIEFING},
        ),
    ]
    found = find_inflight_user_message(messages)
    assert found is not None
    assert found.content == "real question"


def test_inflight_carried_copy_is_eligible():
    messages = [
        HumanMessage(content="carried before", additional_kwargs={HANDOFF_MARKER: "carried"}),
        AIMessage(content="reply"),
    ]
    found = find_inflight_user_message(messages)
    assert found is not None
    assert found.content == "carried before"


def test_inflight_none_when_no_human_messages():
    assert find_inflight_user_message([AIMessage(content="hi")]) is None


# --- render_summary_input ---


def test_render_summary_input_contains_message_text():
    text = render_summary_input(
        [HumanMessage(content="do the task"), AIMessage(content="working on it")],
        prior_summary_text=None,
        trim_tokens=None,
    )
    assert "do the task" in text
    assert "working on it" in text


def test_render_summary_input_prepends_prior_summary():
    text = render_summary_input(
        [HumanMessage(content="new work")],
        prior_summary_text="old alpha summary",
        trim_tokens=None,
    )
    assert "Previous summary of your earlier work" in text
    assert text.index("old alpha summary") < text.index("new work")


def test_render_summary_input_without_prior_has_no_prior_block():
    text = render_summary_input(
        [HumanMessage(content="new work")], prior_summary_text=None, trim_tokens=None
    )
    assert "Previous summary" not in text


def test_default_prompt_has_messages_placeholder():
    assert "{messages}" in DEFAULT_HANDOFF_SUMMARY_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'autobots_devtools_shared_lib.dynagent.agents.history_middleware'`.

- [ ] **Step 3: Implement the skeleton**

Create `src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py`:

```python
# ABOUTME: IsolatedHistoryMiddleware — per-agent message history for the classic engine.
# ABOUTME: On handoff: eager roll-forward summary, context wipe, briefings, carried user message.

from collections.abc import Sequence
from typing import cast

from langchain.messages import AnyMessage, HumanMessage
from langchain_core.messages.utils import (
    count_tokens_approximately,
    get_buffer_string,
    trim_messages,
)

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)

# Marker key in additional_kwargs identifying synthetic handoff messages.
HANDOFF_MARKER = "dynagent_handoff"
# A briefing (resume summary / handoff payload): engine-generated, never carried
# as the in-flight user message.
BRIEFING = "briefing"
# A carried copy of the in-flight user message: eligible for carrying again.
CARRIED = "carried"

_FALLBACK_MESSAGE_COUNT = 15

DEFAULT_HANDOFF_SUMMARY_PROMPT = """You are preparing a handoff briefing.
Summarize the following agent working transcript for (a) the next agent in the
workflow and (b) a future revisit by the same agent. Preserve: the task being
worked on, decisions made, artifacts produced (files written, context keys set,
identifiers), and any open questions or pending work. Be concise; use plain prose.
Respond ONLY with the summary.

<transcript>
{messages}
</transcript>"""


def find_inflight_user_message(messages: Sequence[AnyMessage]) -> HumanMessage | None:
    """Latest user message eligible for carrying — synthetic briefings never qualify."""
    for msg in reversed(messages):
        if (
            isinstance(msg, HumanMessage)
            and msg.additional_kwargs.get(HANDOFF_MARKER) != BRIEFING
        ):
            return msg
    return None


def render_summary_input(
    messages: Sequence[AnyMessage],
    prior_summary_text: str | None,
    trim_tokens: int | None,
) -> str:
    """Render the summarizer input: optional prior-summary block + trimmed transcript."""
    msgs = list(messages)
    if trim_tokens is not None:
        try:
            msgs = cast(
                "list[AnyMessage]",
                trim_messages(
                    msgs,
                    max_tokens=trim_tokens,
                    token_counter=count_tokens_approximately,
                    strategy="last",
                    start_on="human",
                    allow_partial=True,
                    include_system=True,
                ),
            )
        except Exception:
            # Defensive fallback, mirroring SummarizationMiddleware's behavior.
            msgs = list(messages)[-_FALLBACK_MESSAGE_COUNT:]
    parts: list[str] = []
    if prior_summary_text:
        parts.append(f"Previous summary of your earlier work:\n{prior_summary_text}")
    parts.append(get_buffer_string(msgs, format="xml"))
    return "\n\n".join(parts)
```

(Tasks 2 and 3 extend the top import block — do not pre-import anything unused here; ruff F401 would fail this task's pre-commit hook.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: PASS (all 8).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py tests/unit/test_history_middleware.py
git commit -m "feat: isolated-history helpers (in-flight detection, summary input rendering)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: build_swap_update — the pure swap

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py`
- Test: `tests/unit/test_history_middleware.py`

**Interfaces:**
- Consumes: Task 1 helpers/constants.
- Produces:

```python
def build_swap_update(
    state: Mapping[str, Any],
    *,
    departing: str,
    arriving: str,
    summary_message: BaseMessage,
) -> dict[str, Any]
```

Returns `{"messages": [...], "agent_summaries": {...}, "context_agent": arriving}` where `messages` starts with `RemoveMessage(id=REMOVE_ALL_MESSAGES)`. Never mutates `state`'s containers.

- [ ] **Step 1: Write the failing tests**

Merge into the **top import block** of `tests/unit/test_history_middleware.py` (never mid-file — ruff E402): extend the `langchain.messages` import with `RemoveMessage`, add `from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages`, and extend the `history_middleware` import with `CARRIED` and `build_swap_update`.

Then append:

```python
# --- build_swap_update ---


def _swap_state() -> dict:
    return {
        "messages": [
            HumanMessage(content="do the task"),
            AIMessage(content="working on it"),
        ],
    }


def test_swap_stores_summary_and_switches_context_agent():
    update = build_swap_update(
        _swap_state(), departing="alpha", arriving="beta", summary_message=AIMessage(content="S1")
    )
    assert update["context_agent"] == "beta"
    assert update["agent_summaries"]["alpha"].text == "S1"


def test_swap_messages_start_with_remove_all():
    update = build_swap_update(
        _swap_state(), departing="alpha", arriving="beta", summary_message=AIMessage(content="S1")
    )
    first = update["messages"][0]
    assert isinstance(first, RemoveMessage)
    assert first.id == REMOVE_ALL_MESSAGES


def test_swap_adds_handoff_briefing_and_carries_inflight():
    update = build_swap_update(
        _swap_state(), departing="alpha", arriving="beta", summary_message=AIMessage(content="S1")
    )
    briefings = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == BRIEFING
    ]
    assert len(briefings) == 1
    assert "[Handoff from alpha]" in briefings[0].content
    assert "S1" in briefings[0].content
    carried = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == CARRIED
    ]
    assert len(carried) == 1
    assert carried[0].content == "do the task"


def test_swap_revisit_adds_resume_briefing_first():
    state = _swap_state()
    state["agent_summaries"] = {"beta": AIMessage(content="beta-memory")}
    update = build_swap_update(
        state, departing="alpha", arriving="beta", summary_message=AIMessage(content="S1")
    )
    briefings = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == BRIEFING
    ]
    assert len(briefings) == 2
    assert "[Resuming as beta]" in briefings[0].content
    assert "beta-memory" in briefings[0].content
    assert "[Handoff from alpha]" in briefings[1].content


def test_swap_briefings_are_never_recarried():
    state = {
        "messages": [
            HumanMessage(content="real question"),
            HumanMessage(
                content="[Handoff from gamma] noise",
                additional_kwargs={HANDOFF_MARKER: BRIEFING},
            ),
        ]
    }
    update = build_swap_update(
        state, departing="alpha", arriving="beta", summary_message=AIMessage(content="S1")
    )
    carried = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == CARRIED
    ]
    assert len(carried) == 1
    assert carried[0].content == "real question"


def test_swap_without_inflight_has_no_carried_message():
    update = build_swap_update(
        {"messages": [AIMessage(content="only ai")]},
        departing="alpha",
        arriving="beta",
        summary_message=AIMessage(content="S1"),
    )
    carried = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == CARRIED
    ]
    assert carried == []


def test_swap_does_not_mutate_state_containers():
    state = _swap_state()
    state["agent_summaries"] = {}
    build_swap_update(
        state, departing="alpha", arriving="beta", summary_message=AIMessage(content="S1")
    )
    assert state["agent_summaries"] == {}
    assert len(state["messages"]) == 2


def test_swap_wipes_via_add_messages_reducer():
    existing = [
        HumanMessage(content="do the task", id="m1"),
        AIMessage(content="working on it", id="m2"),
    ]
    update = build_swap_update(
        {"messages": existing},
        departing="alpha",
        arriving="beta",
        summary_message=AIMessage(content="S1"),
    )
    merged = add_messages(existing, update["messages"])
    assert all(m.id not in {"m1", "m2"} for m in merged)
    contents = [str(m.content) for m in merged]
    assert any("[Handoff from alpha]" in c for c in contents)
    assert contents[-1] == "do the task"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: new tests FAIL with `ImportError: cannot import name 'build_swap_update'`; Task 1 tests still pass.

- [ ] **Step 3: Implement build_swap_update**

Extend the imports at the top of `history_middleware.py`: add `Mapping` to the `collections.abc` import, add `Any` to the `typing` import, add `RemoveMessage` to the `langchain.messages` import, and add these two lines:

```python
from langchain_core.messages import BaseMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
```

Then append:

```python
def build_swap_update(
    state: Mapping[str, Any],
    *,
    departing: str,
    arriving: str,
    summary_message: BaseMessage,
) -> dict[str, Any]:
    """Compute the state update for one isolated-history swap.

    Full wipe + optional resume briefing (revisit memory) + handoff briefing +
    carried copy of the in-flight user message. Never mutates `state`'s
    containers; briefing messages are built fresh so no message id ever
    re-enters `messages` after a wipe.
    """
    live: list[AnyMessage] = list(state.get("messages") or [])
    summaries: dict[str, BaseMessage] = dict(state.get("agent_summaries") or {})
    resume = summaries.get(arriving)
    summaries[departing] = summary_message

    fresh: list[BaseMessage] = [RemoveMessage(id=REMOVE_ALL_MESSAGES)]
    if resume is not None:
        fresh.append(
            HumanMessage(
                content=(
                    f"[Resuming as {arriving}] Summary of your previous work:\n{resume.text}"
                ),
                additional_kwargs={HANDOFF_MARKER: BRIEFING},
            )
        )
    fresh.append(
        HumanMessage(
            content=f"[Handoff from {departing}]\n{summary_message.text}",
            additional_kwargs={HANDOFF_MARKER: BRIEFING},
        )
    )
    inflight = find_inflight_user_message(live)
    if inflight is not None:
        fresh.append(
            HumanMessage(content=inflight.content, additional_kwargs={HANDOFF_MARKER: CARRIED})
        )

    logger.info(
        f"Isolated handoff: {departing} -> {arriving} (revisit={resume is not None})"
    )
    return {"messages": fresh, "agent_summaries": summaries, "context_agent": arriving}
```

Note: `resume` is read **before** storing the departing summary so a departing agent's fresh summary can never masquerade as the arriving agent's memory (they are different agents here; the middleware never calls this for self-handoff).

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: PASS (all 16).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py tests/unit/test_history_middleware.py
git commit -m "feat: build_swap_update — wipe, briefings, carried in-flight message

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: IsolatedHistoryMiddleware — detection, summarize, hooks

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py`
- Test: `tests/unit/test_history_middleware.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `class IsolatedHistoryState(AgentState)` with `agent_name`, `agent_summaries: dict[str, BaseMessage]`, `context_agent` (all `NotRequired`)
  - `class IsolatedHistoryMiddleware(AgentMiddleware[...])` with `state_schema = IsolatedHistoryState`, `__init__(model, *, summary_prompt=DEFAULT_HANDOFF_SUMMARY_PROMPT, trim_tokens_to_summarize=4000)`, `before_model`, `abefore_model`, `_summarize(str) -> AIMessage`, `_asummarize(str) -> AIMessage`

- [ ] **Step 1: Write the failing tests**

Merge into the **top import block** of `tests/unit/test_history_middleware.py`:

```python
from typing import Any, cast

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
```

and extend the `history_middleware` import with `IsolatedHistoryMiddleware` and `IsolatedHistoryState` (the state annotation keeps pyright's TypedDict assignability checks happy on `state` variables below).

Then append:

```python
# --- IsolatedHistoryMiddleware ---

# The middleware never reads runtime; an Any-typed None keeps pyright quiet in tests.
RT = cast("Any", None)


def _silent_middleware() -> IsolatedHistoryMiddleware:
    """Middleware whose model explodes if ever invoked (empty message iterator)."""
    return IsolatedHistoryMiddleware(model=GenericFakeChatModel(messages=iter([])))


def test_first_model_call_sets_context_agent():
    mw = _silent_middleware()
    update = mw.before_model({"messages": [], "agent_name": "alpha"}, RT)
    assert update == {"context_agent": "alpha"}


def test_same_agent_is_noop():
    mw = _silent_middleware()
    state: IsolatedHistoryState = {
        "messages": [],
        "agent_name": "alpha",
        "context_agent": "alpha",
    }
    assert mw.before_model(state, RT) is None


def test_missing_agent_name_is_noop():
    mw = _silent_middleware()
    assert mw.before_model({"messages": []}, RT) is None


def test_swap_wires_summary_into_update(monkeypatch):
    mw = _silent_middleware()
    monkeypatch.setattr(mw, "_summarize", lambda text: AIMessage(content=f"SUM[{text[:11]}]"))
    state: IsolatedHistoryState = {
        "messages": [HumanMessage(content="do the task"), AIMessage(content="working on it")],
        "agent_name": "beta",
        "context_agent": "alpha",
    }
    update = mw.before_model(state, RT)
    assert update is not None
    assert update["context_agent"] == "beta"
    assert isinstance(update["messages"][0], RemoveMessage)
    assert update["agent_summaries"]["alpha"].text.startswith("SUM[")


def test_swap_folds_prior_summary_into_summarizer_input(monkeypatch):
    captured: list[str] = []

    def fake_summarize(text: str) -> AIMessage:
        captured.append(text)
        return AIMessage(content="S2")

    mw = _silent_middleware()
    monkeypatch.setattr(mw, "_summarize", fake_summarize)
    state: IsolatedHistoryState = {
        "messages": [HumanMessage(content="new work")],
        "agent_name": "beta",
        "context_agent": "alpha",
        "agent_summaries": {"alpha": AIMessage(content="old alpha summary")},
    }
    mw.before_model(state, RT)
    assert len(captured) == 1
    assert "old alpha summary" in captured[0]
    assert "new work" in captured[0]


async def test_async_swap_uses_async_summarizer(monkeypatch):
    async def fake_asummarize(_text: str) -> AIMessage:
        return AIMessage(content="ASYNC-SUM")

    mw = _silent_middleware()
    monkeypatch.setattr(mw, "_asummarize", fake_asummarize)
    state: IsolatedHistoryState = {
        "messages": [HumanMessage(content="do the task")],
        "agent_name": "beta",
        "context_agent": "alpha",
    }
    update = await mw.abefore_model(state, RT)
    assert update is not None
    assert update["agent_summaries"]["alpha"].text == "ASYNC-SUM"


def test_summarize_returns_model_message():
    mw = IsolatedHistoryMiddleware(
        model=GenericFakeChatModel(messages=iter([AIMessage(content="the summary")]))
    )
    result = mw._summarize("some transcript")
    assert isinstance(result, AIMessage)
    assert result.text == "the summary"


def test_summarize_never_raises_on_model_failure():
    mw = _silent_middleware()  # exhausted iterator -> model.invoke raises
    result = mw._summarize("some transcript")
    assert isinstance(result, AIMessage)
    assert "summary unavailable" in result.text


def test_state_schema_merges_via_create_agent():
    from langchain.agents import create_agent

    from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

    model = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    mw = IsolatedHistoryMiddleware(model=model)
    agent = create_agent(model, tools=[], state_schema=Dynagent, middleware=[mw])
    out = agent.invoke({"messages": [HumanMessage(content="hi")], "agent_name": "alpha"})
    assert out["context_agent"] == "alpha"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: new tests FAIL with `ImportError: cannot import name 'IsolatedHistoryMiddleware'`; earlier tests still pass.

- [ ] **Step 3: Implement the middleware**

Extend the imports at the top of `history_middleware.py`: add `NotRequired` to the `typing` import, add `AIMessage` to the `langchain.messages` import, and add these lines:

```python
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.chat_models import BaseChatModel
from langgraph.runtime import Runtime
```

Then append:

```python
class IsolatedHistoryState(AgentState):
    """State extension merged into the agent schema when the middleware is installed.

    `context_agent` is the agent whose context currently occupies `messages`;
    `agent_summaries` maps agent name to the summarizer's raw AIMessage (its
    `.text` is the rolling summary; provenance metadata rides along).
    """

    agent_name: NotRequired[str]
    agent_summaries: NotRequired[dict[str, BaseMessage]]
    context_agent: NotRequired[str]


class IsolatedHistoryMiddleware(AgentMiddleware[IsolatedHistoryState, Any, Any]):
    """Per-agent history isolation for the classic engine (ADR 0002).

    Detects agent transitions (`agent_name` vs `context_agent`) in
    before_model and swaps contexts: eagerly summarizes the departing agent's
    live slice (rolling its prior summary forward), wipes `messages`, and
    briefs the arriving agent. The `handoff` tool is untouched; use cases opt
    in at the call site:

        create_base_agent(middleware=[IsolatedHistoryMiddleware(model=lm())])
    """

    state_schema = IsolatedHistoryState

    def __init__(
        self,
        model: BaseChatModel,
        *,
        summary_prompt: str = DEFAULT_HANDOFF_SUMMARY_PROMPT,
        trim_tokens_to_summarize: int | None = 4000,
    ) -> None:
        super().__init__()
        self.model = model
        self.summary_prompt = summary_prompt
        self.trim_tokens_to_summarize = trim_tokens_to_summarize

    def _summary_input(self, state: Mapping[str, Any], departing: str) -> str:
        prior = (state.get("agent_summaries") or {}).get(departing)
        return render_summary_input(
            state.get("messages") or [],
            prior.text if prior is not None else None,
            self.trim_tokens_to_summarize,
        )

    def _summarize(self, summary_input: str) -> AIMessage:
        """One sync LLM call; never raises — handoff continuity over summary fidelity."""
        try:
            response = self.model.invoke(
                self.summary_prompt.format(messages=summary_input),
                config={"metadata": {"lc_source": "isolated_history"}},
            )
        except Exception as exc:
            logger.warning(f"Isolated-history summary failed: {exc}")
            return AIMessage(content=f"(summary unavailable: {exc})")
        return cast("AIMessage", response)

    async def _asummarize(self, summary_input: str) -> AIMessage:
        """One async LLM call; never raises — handoff continuity over summary fidelity."""
        try:
            response = await self.model.ainvoke(
                self.summary_prompt.format(messages=summary_input),
                config={"metadata": {"lc_source": "isolated_history"}},
            )
        except Exception as exc:
            logger.warning(f"Isolated-history summary failed: {exc}")
            return AIMessage(content=f"(summary unavailable: {exc})")
        return cast("AIMessage", response)

    def before_model(
        self,
        state: IsolatedHistoryState,
        runtime: Runtime[Any],  # noqa: ARG002 — hook signature fixed by AgentMiddleware
    ) -> dict[str, Any] | None:
        arriving = state.get("agent_name")
        if not arriving:
            return None
        context_agent = state.get("context_agent")
        if context_agent is None:
            return {"context_agent": arriving}
        if context_agent == arriving:
            return None
        summary_message = self._summarize(self._summary_input(state, context_agent))
        return build_swap_update(
            state, departing=context_agent, arriving=arriving, summary_message=summary_message
        )

    async def abefore_model(
        self,
        state: IsolatedHistoryState,
        runtime: Runtime[Any],  # noqa: ARG002 — hook signature fixed by AgentMiddleware
    ) -> dict[str, Any] | None:
        arriving = state.get("agent_name")
        if not arriving:
            return None
        context_agent = state.get("context_agent")
        if context_agent is None:
            return {"context_agent": arriving}
        if context_agent == arriving:
            return None
        summary_message = await self._asummarize(self._summary_input(state, context_agent))
        return build_swap_update(
            state, departing=context_agent, arriving=arriving, summary_message=summary_message
        )
```

If pyright rejects the `AgentMiddleware[IsolatedHistoryState, Any, Any]` parameterization (generic arity differs in a future langchain), fall back to the unparameterized `class IsolatedHistoryMiddleware(AgentMiddleware):` — the runtime behavior is identical.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: PASS (all 25).

- [ ] **Step 5: Run the whole unit suite to catch regressions**

Run: `../.venv/bin/pytest tests/unit -x -q --no-cov`
Expected: PASS — nothing in the shared path changed.

- [ ] **Step 6: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/history_middleware.py tests/unit/test_history_middleware.py
git commit -m "feat: IsolatedHistoryMiddleware — detection, eager summaries, sync+async hooks

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Public export

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/__init__.py`
- Test: `tests/unit/test_history_middleware.py`

**Interfaces:**
- Produces: `from autobots_devtools_shared_lib.dynagent import IsolatedHistoryMiddleware` for use cases.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_history_middleware.py`:

```python
# --- public export ---


def test_dynagent_package_exports_middleware():
    import autobots_devtools_shared_lib.dynagent as dynagent_pkg

    assert dynagent_pkg.IsolatedHistoryMiddleware is IsolatedHistoryMiddleware
    assert "IsolatedHistoryMiddleware" in dynagent_pkg.__all__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py::test_dynagent_package_exports_middleware -v --no-cov`
Expected: FAIL with `AttributeError: ... has no attribute 'IsolatedHistoryMiddleware'`.

- [ ] **Step 3: Add the export**

In `src/autobots_devtools_shared_lib/dynagent/__init__.py`, add the import in module-name alphabetical order (between the `batch` and `invocation_utils` imports):

```python
from autobots_devtools_shared_lib.dynagent.agents.history_middleware import (
    IsolatedHistoryMiddleware,
)
```

and add `"IsolatedHistoryMiddleware",` to `__all__` (sorted — between `"DynagentSettings"` and `"LLMProvider"`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_middleware.py -v --no-cov`
Expected: PASS (all 26).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/__init__.py tests/unit/test_history_middleware.py
git commit -m "feat: export IsolatedHistoryMiddleware from dynagent package

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Documentation, supersessions, full verification

**Files:**
- Create: `docs/adr/0002-isolated-history-via-middleware.md`
- Modify: `docs/adr/0001-isolated-history-mode.md` (status line only)
- Create: `docs/features/isolated-history.md`
- Modify: `docs/superpowers/plans/2026-07-17-isolated-history-mode.md` (banner only)

- [ ] **Step 1: Write ADR 0002**

Create `docs/adr/0002-isolated-history-via-middleware.md`:

```markdown
# Isolated history via middleware: eager summaries, no archives

Status: accepted (supersedes 0001)

Per-agent history isolation is one self-contained `IsolatedHistoryMiddleware`
(`dynagent/agents/history_middleware.py`), opted into at the `create_base_agent`
call site — not a `history_mode` YAML key, not a branch in the `handoff` tool.
Three decisions will surprise future readers:

## Detection in before_model, not in the handoff tool

The `handoff` tool keeps its legacy shape (ToolMessage + `agent_name` update).
The middleware compares `agent_name` against its own `context_agent` state key
on every model call and performs the swap when they differ. Because this runs
after all ToolMessages of the previous turn have landed, handoff may share its
AI turn with other tool calls (ADR 0001's sole-tool-call limitation is gone),
and self-handoff is a natural no-op.

## Eager roll-forward summaries; no archives

On every swap the departing agent's live slice is summarized immediately
(folding its prior summary), costing one LLM call per handoff. We dropped
ADR 0001's lazy summaries + `agent_archives` because their only remaining
purpose was laziness once transcript reassembly and raw-history retrieval were
cut from requirements. Consequences accepted deliberately: `state["messages"]`
is not the full conversation (already true under `SummarizationMiddleware`
compaction), there is no `get_my_history`, and no `reassemble_transcript`.

## State via middleware state_schema; summaries are BaseMessages

`agent_summaries: dict[str, BaseMessage]` and `context_agent` live on
`IsolatedHistoryState`, merged into the agent schema by `create_agent` — the
`Dynagent` TypedDict is untouched and the keys exist only when the middleware
is installed. The stored value is the summarizer's raw `AIMessage` (text plus
provenance/usage metadata); briefing messages are always built fresh from its
`.text` so no message id re-enters `messages` after a wipe.

## Consequences

- Cross-agent channel is the handoff briefing plus a revisit's resume
  briefing; the in-flight user message always carries.
- The global `SummarizationMiddleware` stays as a mid-visit safety net; it
  runs before this middleware in the stack, so a rare same-turn double fire
  wastes one summary call but stays correct.
- Classic engine only; the deep engine isolates subagent contexts by
  construction.
```

- [ ] **Step 2: Mark ADR 0001 superseded**

In `docs/adr/0001-isolated-history-mode.md`, change the line `Status: accepted` to:

```markdown
Status: superseded by [0002](0002-isolated-history-via-middleware.md)
```

- [ ] **Step 3: Write the feature doc**

Create `docs/features/isolated-history.md`:

````markdown
# Isolated History (middleware)

Per-agent message history for the classic engine. Design rationale:
[ADR 0002](../adr/0002-isolated-history-via-middleware.md); spec:
`docs/superpowers/specs/2026-07-18-isolated-history-middleware-design.md`.

## Enabling (call site, not YAML)

```python
from autobots_devtools_shared_lib.dynagent import (
    IsolatedHistoryMiddleware,
    create_base_agent,
    lm,
)

agent = create_base_agent(
    checkpointer=checkpointer,
    middleware=[IsolatedHistoryMiddleware(model=lm())],
)
```

Optional constructor knobs: `summary_prompt` (must contain `{messages}`) and
`trim_tokens_to_summarize` (default 4000; `None` disables trimming).

## Semantics

| Concern | Behavior |
|---|---|
| Detection | `before_model` compares `agent_name` (written by the untouched `handoff` tool) with `context_agent`; a difference triggers the swap |
| On swap | Departing agent's context is summarized eagerly (one LLM call, prior summary folded in) into `agent_summaries[departing]`, then `messages` is wiped |
| Arriving context | Optional `[Resuming as X]` briefing (revisit memory) + `[Handoff from Y]` briefing + a carried copy of the in-flight user message |
| Self-handoff | No-op (agent name unchanged) |
| Sibling tool calls | Safe — the swap runs after all ToolMessages have landed |
| Summary failure | Never breaks the handoff; the briefing carries a `(summary unavailable: ...)` placeholder |
| `state["messages"]` | The current agent's working context only — not the full conversation (same class of behavior as `SummarizationMiddleware` compaction) |

## Constraints

- The global `SummarizationMiddleware` still runs (before this middleware in
  the stack); if a handoff coincides with its token trigger, one summary call
  is wasted but behavior stays correct.
- Classic engine only; the deep engine isolates subagent contexts by
  construction.
````

- [ ] **Step 4: Mark the old plan superseded**

At the very top of `docs/superpowers/plans/2026-07-17-isolated-history-mode.md` (above the `#` title), insert:

```markdown
> **SUPERSEDED — do not execute.** Replaced by
> `docs/superpowers/plans/2026-07-18-isolated-history-middleware.md` per the approved spec
> `docs/superpowers/specs/2026-07-18-isolated-history-middleware-design.md`.

```

- [ ] **Step 5: Run the full check suite**

```bash
make check-format && make type-check && make test
```

Expected: ruff format --check clean, ruff check clean, pyright clean, all tests pass. If formatting drift surfaces, run `make format` and re-check.

- [ ] **Step 6: Commit**

```bash
git add docs/adr/0002-isolated-history-via-middleware.md docs/adr/0001-isolated-history-mode.md docs/features/isolated-history.md docs/superpowers/plans/2026-07-17-isolated-history-mode.md
git commit -m "docs: ADR 0002 + feature guide for isolated history via middleware

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Final verification of the branch**

```bash
git log --oneline main..HEAD
```

Expected: 5 commits (Task 0 produces none), scoped as above. Do not merge or push — integration is decided by the user (superpowers:finishing-a-development-branch).
