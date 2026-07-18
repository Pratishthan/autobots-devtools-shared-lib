# Isolated History Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-agent message history in the classic Dynagent engine: on handoff the departing agent's live slice is archived, the arriving agent starts fresh with a configurable payload (summary/full/none), revisited agents restore their own rolling summary, and the user-facing transcript is reassembled from archives.

**Architecture:** A domain opts in with a top-level `history_mode: isolated` key in `agents.yaml`. The `handoff` tool branches on that mode: in isolated mode it returns a `Command` whose update wipes `messages` (via `RemoveMessage(id=REMOVE_ALL_MESSAGES)`), writes the departing agent's slice into a new `agent_archives` state key, lazily maintains rolling summaries in `agent_summaries`, and assembles the arriving agent's fresh context. All history logic lives in a new pure module `dynagent/services/history.py` (LLM call injected as a callable) so it is unit-testable without a model. Design decisions are recorded in `docs/adr/0001-isolated-history-mode.md` — read it before starting.

**Tech Stack:** Python 3.12, langchain 1.3.11 / langgraph (installed in the shared workspace venv `../.venv`), pytest (`asyncio_mode = "auto"`), ruff, pyright.

## Global Constraints

- All work happens inside the repo `autobots-devtools-shared-lib` (its own git repo — commit from inside it, never from the workspace root; pre-commit hooks run ruff + pyright + pytest + poetry check).
- Python 3.12+, ruff line-length 100, double quotes; pyright basic mode.
- Run commands from `autobots-devtools-shared-lib/` with the shared venv active: `source ../.venv/bin/activate` (or prefix commands with `../.venv/bin/`).
- Verbatim vocabulary (from `CONTEXT.md`): Visit, Live Slice, Archive, Agent Summary, Handoff Payload, Payload Flag, In-flight User Message, Transcript. Use these names in code and docstrings.
- YAML keys (exact): top-level `history_mode: shared | isolated` (default `shared`); per-agent `handoff_payload: summary | full | none` (default `summary`); per-agent `summary_prompt: <prompt-file-name>` (optional, resolves like the `prompt:` key to `prompts/<name>.md`).
- Classic engine only — do not touch `base_deepagent.py`, `deep_state.py`, or any `deep_*` module.
- The existing shared-history behavior must be byte-for-byte unchanged when `history_mode` is absent or `shared` — all existing tests must keep passing untouched.
- Imports verified against the installed venv: `from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage, ToolMessage`, `from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages`. `message.text` is a property (NOT a method — calling it is deprecated).

## File Structure

| File | Responsibility |
|---|---|
| `src/autobots_devtools_shared_lib/dynagent/models/state.py` (modify) | `Visit` + `AgentSummary` TypedDicts, 3 new `Dynagent` keys |
| `src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py` (modify) | Parse + validate `history_mode`, `handoff_payload`, `summary_prompt`; accessors |
| `src/autobots_devtools_shared_lib/dynagent/agents/agent_meta.py` (modify) | Expose `history_mode`, `handoff_payload_map`, `summary_prompt_map` |
| `src/autobots_devtools_shared_lib/dynagent/services/history.py` (create) | All isolated-history logic: rendering, rolling summaries, fresh-context assembly, transcript reassembly, LLM summarizer wrapper |
| `src/autobots_devtools_shared_lib/dynagent/tools/state_tools.py` (modify) | `handoff` branches on mode via `perform_handoff`; new `get_my_history` tool |
| `src/autobots_devtools_shared_lib/dynagent/tools/tool_registry.py` (modify) | Register `get_my_history` as a default tool |
| `src/autobots_devtools_shared_lib/dynagent/__init__.py` (modify) | Export `reassemble_transcript` |
| `tests/unit/test_dynagent_state.py` (modify) | State-key tests |
| `tests/unit/test_history_config.py` (create) | Config parsing/validation + AgentMeta tests |
| `tests/unit/test_history_service.py` (create) | Pure history-logic tests |
| `tests/unit/test_state_tools.py` (modify) | `perform_handoff` mode-branch + `get_my_history` tests |
| `tests/unit/test_tool_registry.py` (modify) | Registry includes `get_my_history` |
| `docs/features/isolated-history.md` (create) | Usage documentation |

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

```bash
cd /Users/pralhad/work/src/ws-autobots/autobots-devtools-shared-lib
git checkout -b feat/isolated-history-mode
```

---

### Task 1: State schema — Visit, AgentSummary, new Dynagent keys

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/models/state.py`
- Test: `tests/unit/test_dynagent_state.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Visit` (TypedDict: `order: int`, `agent: str`, `messages: list[AnyMessage]`), `AgentSummary` (TypedDict: `text: str`, `through: int`), and `Dynagent` keys `agent_archives: NotRequired[dict[str, list[Visit]]]`, `agent_summaries: NotRequired[dict[str, AgentSummary]]`, `visit_counter: NotRequired[int]`. `through` is the highest global visit `order` the summary covers. All later tasks import `Visit` and `AgentSummary` from `autobots_devtools_shared_lib.dynagent.models.state`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_dynagent_state.py`:

```python
# --- Isolated-history state keys ---


def test_dynagent_declares_isolated_history_keys():
    from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

    annotations = Dynagent.__annotations__
    assert "agent_archives" in annotations
    assert "agent_summaries" in annotations
    assert "visit_counter" in annotations


def test_visit_and_agent_summary_shapes():
    from autobots_devtools_shared_lib.dynagent.models.state import AgentSummary, Visit

    visit: Visit = {"order": 1, "agent": "coordinator", "messages": []}
    summary: AgentSummary = {"text": "did things", "through": 1}
    assert visit["agent"] == "coordinator"
    assert summary["through"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_dynagent_state.py -v --no-cov`
Expected: the two new tests FAIL (`ImportError` / `KeyError`); existing tests pass.

- [ ] **Step 3: Implement the state schema**

Replace the full contents of `src/autobots_devtools_shared_lib/dynagent/models/state.py` with:

```python
# ABOUTME: State schema for the dynagent reference architecture.
# ABOUTME: Dynagent holds routing keys plus isolated-history archives and summaries.

from typing import NotRequired, TypedDict

from langchain.agents import AgentState
from langchain.messages import AnyMessage


class Visit(TypedDict):
    """One archived Visit: the Live Slice an agent held between arrival and departure.

    `order` is the global departure sequence within the session, used to
    reassemble the Transcript chronologically.
    """

    order: int
    agent: str
    messages: list[AnyMessage]


class AgentSummary(TypedDict):
    """Rolling Agent Summary; `through` is the highest Visit order it covers."""

    text: str
    through: int


class Dynagent(AgentState):
    """Minimal agent state carrying routing keys and optional user identity.

    In isolated history mode (see docs/adr/0001-isolated-history-mode.md),
    `agent_archives` holds each agent's past Visits, `agent_summaries` the
    rolling summaries, and `visit_counter` the global departure sequence.
    """

    agent_name: NotRequired[str]
    session_id: NotRequired[str]
    user_name: NotRequired[str]
    agent_archives: NotRequired[dict[str, list[Visit]]]
    agent_summaries: NotRequired[dict[str, AgentSummary]]
    visit_counter: NotRequired[int]
```

If ruff's TC rules flag the `AnyMessage` import, keep it at runtime (TypedDict annotations are evaluated at class-creation time) with a trailing `# noqa: TC002` rather than moving it into `TYPE_CHECKING`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_dynagent_state.py -v --no-cov`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/models/state.py tests/unit/test_dynagent_state.py
git commit -m "feat: add isolated-history state keys (Visit, AgentSummary, archives)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Config — history_mode, handoff_payload, summary_prompt

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py`
- Modify: `src/autobots_devtools_shared_lib/dynagent/agents/agent_meta.py`
- Test: `tests/unit/test_history_config.py` (create)

**Interfaces:**
- Consumes: existing `load_agents_config()`, `load_prompt(name)`, `_reset_agent_config()`, `AgentConfig`.
- Produces:
  - `AgentConfig.handoff_payload: str` (default `"summary"`), `AgentConfig.summary_prompt: str | None` (default `None`)
  - `get_history_mode() -> str` (returns `"shared"` or `"isolated"`)
  - `get_handoff_payload_map() -> dict[str, str]`
  - `get_summary_prompt_map() -> dict[str, str | None]` (values are **loaded prompt text**, not file names)
  - `AgentMeta.history_mode: str`, `AgentMeta.handoff_payload_map: dict[str, str]`, `AgentMeta.summary_prompt_map: dict[str, str | None]`
  - `load_agents_config()` raises `ValueError` on invalid `history_mode` or `handoff_payload` values.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_history_config.py`:

```python
# ABOUTME: Unit tests for isolated-history configuration parsing and validation.
# ABOUTME: Covers history_mode, handoff_payload, summary_prompt, and AgentMeta exposure.

import textwrap
from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.agents import agent_config_utils
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    _reset_agent_config,
    get_handoff_payload_map,
    get_history_mode,
    get_summary_prompt_map,
    load_agents_config,
)
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta


def write_config(
    tmp_path: Path,
    history_mode: str | None = "isolated",
    alpha_extra: str = "",
    beta_extra: str = "handoff_payload: none",
) -> Path:
    prompts = tmp_path / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "alpha.md").write_text("You are alpha.")
    (prompts / "beta.md").write_text("You are beta.")
    (prompts / "alpha-summary.md").write_text("Summarize alpha's work briefly.")
    header = f"history_mode: {history_mode}\n" if history_mode is not None else ""
    body = textwrap.dedent(f"""\
        agents:
          alpha:
            prompt: alpha
            tools: []
            is_default: true
            summary_prompt: alpha-summary
            {alpha_extra}
          beta:
            prompt: beta
            tools: []
            {beta_extra}
    """)
    (tmp_path / "agents.yaml").write_text(header + body)
    return tmp_path


@pytest.fixture(autouse=True)
def _clean_config():
    _reset_agent_config()
    AgentMeta.reset()
    yield
    _reset_agent_config()
    AgentMeta.reset()


def _point_at(monkeypatch, config_dir: Path) -> None:
    monkeypatch.setattr(agent_config_utils, "get_config_dir", lambda: config_dir)


def test_history_mode_defaults_to_shared(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path, history_mode=None))
    assert get_history_mode() == "shared"


def test_history_mode_isolated_parsed(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path, history_mode="isolated"))
    assert get_history_mode() == "isolated"


def test_invalid_history_mode_raises(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path, history_mode="bogus"))
    with pytest.raises(ValueError, match="history_mode"):
        load_agents_config()


def test_handoff_payload_defaults_to_summary(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path))
    assert get_handoff_payload_map()["alpha"] == "summary"


def test_handoff_payload_explicit_none(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path))
    assert get_handoff_payload_map()["beta"] == "none"


def test_invalid_handoff_payload_raises(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path, beta_extra="handoff_payload: everything"))
    with pytest.raises(ValueError, match="handoff_payload"):
        load_agents_config()


def test_summary_prompt_map_loads_text(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path))
    prompt_map = get_summary_prompt_map()
    assert prompt_map["alpha"] == "Summarize alpha's work briefly."
    assert prompt_map["beta"] is None


def test_agent_meta_exposes_history_config(monkeypatch, tmp_path):
    _point_at(monkeypatch, write_config(tmp_path))
    meta = AgentMeta.instance()
    assert meta.history_mode == "isolated"
    assert meta.handoff_payload_map == {"alpha": "summary", "beta": "none"}
    assert meta.summary_prompt_map["alpha"] == "Summarize alpha's work briefly."
```

Note: `write_config`'s f-string indentation places `alpha_extra`/`beta_extra` at the correct YAML nesting because the placeholder sits inside the dedented block at agent-field depth. Empty extras leave a harmless blank line.

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_config.py -v --no-cov`
Expected: FAIL with `ImportError: cannot import name 'get_history_mode'`.

- [ ] **Step 3: Implement config parsing**

In `src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py`:

3a. Add two module constants near `_ENV_VAR_PATTERN` (line ~52):

```python
_VALID_HISTORY_MODES = {"shared", "isolated"}
_VALID_HANDOFF_PAYLOADS = {"summary", "full", "none"}
```

3b. Add two fields to `AgentConfig` (after `debug: bool = False`, line ~106):

```python
    # --- isolated-history fields (read only when history_mode: isolated) ---
    handoff_payload: str = "summary"
    summary_prompt: str | None = None
```

3c. In `AgentConfig.from_dict`, add to the `cls(...)` call (after `debug=...`):

```python
            handoff_payload=data.get("handoff_payload", "summary"),
            summary_prompt=data.get("summary_prompt"),
```

3d. Add a module global next to `_GLOBAL_MCP_SERVERS` (line ~169):

```python
_GLOBAL_HISTORY_MODE: str = "shared"
```

3e. In `_reset_agent_config()`, reset it (extend the existing `global` statement and body):

```python
def _reset_agent_config() -> None:
    """Clear the cached agent config — for test isolation."""
    global _GLOBAL_AGENT_CONFIG, _GLOBAL_MODEL_PROFILES, _GLOBAL_BACKEND_CONFIG, _GLOBAL_MCP_SERVERS
    global _GLOBAL_HISTORY_MODE
    _GLOBAL_AGENT_CONFIG = {}
    _GLOBAL_MODEL_PROFILES = {}
    _GLOBAL_BACKEND_CONFIG = None
    _GLOBAL_MCP_SERVERS = {}
    _GLOBAL_HISTORY_MODE = "shared"
```

3f. In `load_agents_config()`: add `_GLOBAL_HISTORY_MODE` to the function's `global` statement (add a second line `global _GLOBAL_HISTORY_MODE` under the existing one), then directly after the `_GLOBAL_MCP_SERVERS = data.get("mcp_servers") or {}` line insert:

```python
    history_mode = data.get("history_mode", "shared")
    if history_mode not in _VALID_HISTORY_MODES:
        msg = (
            f"history_mode must be one of {sorted(_VALID_HISTORY_MODES)}, "
            f"got {history_mode!r}"
        )
        raise ValueError(msg)
    _GLOBAL_HISTORY_MODE = history_mode
```

3g. After the agents dict is built (right after the `for agent_id, agent_data in data.get("agents", {}).items():` loop completes), insert the payload validation:

```python
    for agent_id, agent_cfg in agents.items():
        if agent_cfg.handoff_payload not in _VALID_HANDOFF_PAYLOADS:
            msg = (
                f"Agent '{agent_id}': handoff_payload must be one of "
                f"{sorted(_VALID_HANDOFF_PAYLOADS)}, got {agent_cfg.handoff_payload!r}"
            )
            raise ValueError(msg)
```

3h. Add three accessors at the end of the file:

```python
def get_history_mode() -> str:
    """Return the domain's history mode: 'shared' (default) or 'isolated'."""
    load_agents_config()
    return _GLOBAL_HISTORY_MODE


def get_handoff_payload_map() -> dict[str, str]:
    """Return {agent_name: Payload Flag ('summary' | 'full' | 'none')}."""
    return {name: c.handoff_payload for name, c in load_agents_config().items()}


def get_summary_prompt_map() -> dict[str, str | None]:
    """Return {agent_name: loaded summary prompt text, or None to use the default}."""
    return {
        name: (load_prompt(c.summary_prompt) if c.summary_prompt else None)
        for name, c in load_agents_config().items()
    }
```

3i. Add `"get_handoff_payload_map"`, `"get_history_mode"`, `"get_summary_prompt_map"` to `__all__` (keep it sorted).

3j. In `src/autobots_devtools_shared_lib/dynagent/agents/agent_meta.py`: add class-level annotations after `mcp_servers_config: dict[str, dict[str, Any]]`:

```python
    history_mode: str
    handoff_payload_map: dict[str, str]
    summary_prompt_map: dict[str, str | None]
```

and in `__init__` after `self.mcp_servers_config = ...`:

```python
        self.history_mode = _agent_config.get_history_mode()
        self.handoff_payload_map = _agent_config.get_handoff_payload_map()
        self.summary_prompt_map = _agent_config.get_summary_prompt_map()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_config.py tests/unit/test_agent_config_utils.py tests/unit/test_agent_meta.py -v --no-cov`
Expected: PASS (new tests plus all pre-existing config/meta tests — proves the `shared` default breaks nothing).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/agents/agent_config_utils.py src/autobots_devtools_shared_lib/dynagent/agents/agent_meta.py tests/unit/test_history_config.py
git commit -m "feat: parse history_mode, handoff_payload, summary_prompt config

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: History service — pure helpers

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/services/history.py`
- Test: `tests/unit/test_history_service.py` (create)

**Interfaces:**
- Consumes: `Visit`, `AgentSummary` from Task 1.
- Produces (all in `autobots_devtools_shared_lib.dynagent.services.history`):
  - `HANDOFF_MARKER = "dynagent_handoff"`, `BRIEFING = "briefing"`, `CARRIED = "carried"`, `DEFAULT_SUMMARY_PROMPT: str`
  - `Summarize = Callable[[str, str], str]` — `(prompt_text, transcript_text) -> summary_text`
  - `render_transcript(messages: Sequence[AnyMessage]) -> str`
  - `find_inflight_user_message(messages: Sequence[AnyMessage]) -> HumanMessage | None`
  - `roll_summary(prior: AgentSummary | None, visits: Sequence[Visit], prompt_text: str, summarize: Summarize) -> AgentSummary`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_history_service.py`:

```python
# ABOUTME: Unit tests for the isolated-history service (pure logic, no LLM).
# ABOUTME: Covers transcript rendering, in-flight detection, and rolling summaries.

from langchain.messages import AIMessage, HumanMessage, ToolMessage

from autobots_devtools_shared_lib.dynagent.services.history import (
    BRIEFING,
    HANDOFF_MARKER,
    find_inflight_user_message,
    render_transcript,
    roll_summary,
)

# --- render_transcript ---


def test_render_transcript_roles_and_text():
    messages = [
        HumanMessage(content="extract the models"),
        AIMessage(content="on it"),
        ToolMessage(content="wrote file", tool_call_id="tc-1"),
    ]
    text = render_transcript(messages)
    assert "human: extract the models" in text
    assert "ai: on it" in text
    assert "tool: wrote file" in text


def test_render_transcript_includes_tool_call_names():
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "handoff", "args": {"next_agent": "beta"}, "id": "tc-9"}],
    )
    text = render_transcript([msg])
    assert "handoff" in text
    assert "beta" in text


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


def test_inflight_none_when_no_human_messages():
    assert find_inflight_user_message([AIMessage(content="hi")]) is None


# --- roll_summary ---


def test_roll_summary_first_visit():
    calls: list[tuple[str, str]] = []

    def fake_summarize(prompt: str, transcript: str) -> str:
        calls.append((prompt, transcript))
        return "summary-1"

    visits = [{"order": 1, "agent": "alpha", "messages": [HumanMessage(content="hi")]}]
    result = roll_summary(None, visits, "PROMPT", fake_summarize)
    assert result == {"text": "summary-1", "through": 1}
    assert len(calls) == 1
    assert calls[0][0] == "PROMPT"
    assert "hi" in calls[0][1]


def test_roll_summary_folds_prior_and_only_uncovered_visits():
    calls: list[str] = []

    def fake_summarize(prompt: str, transcript: str) -> str:
        calls.append(transcript)
        return "summary-2"

    prior = {"text": "old summary", "through": 1}
    visits = [
        {"order": 1, "agent": "alpha", "messages": [HumanMessage(content="covered")]},
        {"order": 3, "agent": "alpha", "messages": [HumanMessage(content="new work")]},
    ]
    result = roll_summary(prior, visits, "PROMPT", fake_summarize)
    assert result == {"text": "summary-2", "through": 3}
    assert "old summary" in calls[0]
    assert "new work" in calls[0]
    assert "covered" not in calls[0]


def test_roll_summary_noop_when_everything_covered():
    def exploding_summarize(prompt: str, transcript: str) -> str:
        raise AssertionError("summarize must not be called")

    prior = {"text": "current", "through": 2}
    visits = [{"order": 2, "agent": "alpha", "messages": []}]
    result = roll_summary(prior, visits, "PROMPT", exploding_summarize)
    assert result == {"text": "current", "through": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_service.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'autobots_devtools_shared_lib.dynagent.services.history'`.

- [ ] **Step 3: Implement the pure helpers**

Create `src/autobots_devtools_shared_lib/dynagent/services/history.py`:

```python
# ABOUTME: Isolated-history primitives: transcript rendering, rolling summaries,
# ABOUTME: and fresh-context assembly used by handoff in isolated mode (ADR 0001).

from collections.abc import Callable, Sequence

from langchain.messages import AIMessage, AnyMessage, HumanMessage

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.models.state import AgentSummary, Visit

logger = get_logger(__name__)

# Marker key in additional_kwargs identifying synthetic handoff messages.
HANDOFF_MARKER = "dynagent_handoff"
# A briefing block (resume summary / handoff payload): never carried as the
# in-flight user message, and hidden from the reassembled Transcript.
BRIEFING = "briefing"
# A carried copy of the In-flight User Message: eligible for carrying again,
# hidden from the Transcript (the original lives in an earlier Visit).
CARRIED = "carried"

DEFAULT_SUMMARY_PROMPT = (
    "Summarize the following agent working transcript for a future revisit and "
    "for the next agent in the workflow. Preserve: the task being worked on, "
    "decisions made, artifacts produced (files written, context keys set, "
    "identifiers), and any open questions or pending work. Be concise; use "
    "plain prose."
)

# (prompt_text, transcript_text) -> summary text
Summarize = Callable[[str, str], str]


def render_transcript(messages: Sequence[AnyMessage]) -> str:
    """Render messages as readable text — summarizer input and `full` payloads."""
    lines: list[str] = []
    for msg in messages:
        role = msg.__class__.__name__.removesuffix("Message").lower()
        text = msg.text or ""
        if isinstance(msg, AIMessage) and msg.tool_calls:
            calls = ", ".join(f"{c['name']}({c['args']})" for c in msg.tool_calls)
            text = f"{text}\n[tool calls: {calls}]".strip()
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def find_inflight_user_message(messages: Sequence[AnyMessage]) -> HumanMessage | None:
    """Latest user message eligible for carrying — synthetic briefings never qualify."""
    for msg in reversed(messages):
        if (
            isinstance(msg, HumanMessage)
            and msg.additional_kwargs.get(HANDOFF_MARKER) != BRIEFING
        ):
            return msg
    return None


def roll_summary(
    prior: AgentSummary | None,
    visits: Sequence[Visit],
    prompt_text: str,
    summarize: Summarize,
) -> AgentSummary:
    """Fold Visits not yet covered by `prior` into a new rolling Agent Summary.

    Only uncovered Visits (order > prior['through']) are summarized, together
    with the prior summary text, so summarizer input stays bounded per hop.
    """
    covered = prior["through"] if prior is not None else 0
    uncovered = [v for v in visits if v["order"] > covered]
    if not uncovered:
        return prior if prior is not None else {"text": "", "through": 0}

    parts: list[str] = []
    if prior is not None and prior["text"]:
        parts.append(f"Previous summary:\n{prior['text']}")
    for visit in uncovered:
        parts.append(f"Visit transcript:\n{render_transcript(visit['messages'])}")
    new_text = summarize(prompt_text, "\n\n".join(parts))
    return {"text": new_text, "through": uncovered[-1]["order"]}
```

(Task 4 will extend these imports with `Mapping`, `Any`, `RemoveMessage`, and `REMOVE_ALL_MESSAGES` — do not import them yet; ruff F401 would fail this task's pre-commit hook.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_service.py -v --no-cov`
Expected: PASS (all 9).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/services/history.py tests/unit/test_history_service.py
git commit -m "feat: history service pure helpers (render, in-flight, rolling summary)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: History service — build_handoff_update

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/services/history.py`
- Test: `tests/unit/test_history_service.py`

**Interfaces:**
- Consumes: Task 3 helpers.
- Produces:

```python
def build_handoff_update(
    state: Mapping[str, Any],
    next_agent: str,
    *,
    payload_flags: Mapping[str, str],
    summary_prompts: Mapping[str, str | None],
    default_agent: str,
    summarize: Summarize,
) -> dict[str, Any]
```

Returns the full `Command` update dict with keys `messages` (starting with `RemoveMessage(id=REMOVE_ALL_MESSAGES)`), `agent_name`, `agent_archives`, `agent_summaries`, `visit_counter`. Never mutates `state`'s nested containers.

- [ ] **Step 1: Write the failing tests**

First merge these into the **top import block** of `tests/unit/test_history_service.py` (never mid-file — ruff E402): extend the `langchain.messages` import with `RemoveMessage`, add `from langgraph.graph.message import REMOVE_ALL_MESSAGES`, and extend the `history` import with `CARRIED` and `build_handoff_update`.

Then append the tests:

```python
# --- build_handoff_update ---


def _fake_summarize(prompt: str, transcript: str) -> str:
    return f"SUM[{transcript[:20]}]"


def _base_state(agent: str = "alpha") -> dict:
    return {
        "agent_name": agent,
        "messages": [
            HumanMessage(content="do the task"),
            AIMessage(content="working on it"),
        ],
    }


def test_first_handoff_archives_departing_slice():
    update = build_handoff_update(
        _base_state(),
        "beta",
        payload_flags={"alpha": "summary"},
        summary_prompts={},
        default_agent="alpha",
        summarize=_fake_summarize,
    )
    assert update["agent_name"] == "beta"
    assert update["visit_counter"] == 1
    visits = update["agent_archives"]["alpha"]
    assert len(visits) == 1
    assert visits[0]["order"] == 1
    assert visits[0]["messages"][0].content == "do the task"


def test_messages_update_starts_with_remove_all():
    update = build_handoff_update(
        _base_state(),
        "beta",
        payload_flags={"alpha": "summary"},
        summary_prompts={},
        default_agent="alpha",
        summarize=_fake_summarize,
    )
    first = update["messages"][0]
    assert isinstance(first, RemoveMessage)
    assert first.id == REMOVE_ALL_MESSAGES


def test_summary_flag_produces_summary_payload_and_stores_it():
    update = build_handoff_update(
        _base_state(),
        "beta",
        payload_flags={"alpha": "summary"},
        summary_prompts={},
        default_agent="alpha",
        summarize=_fake_summarize,
    )
    assert update["agent_summaries"]["alpha"]["through"] == 1
    briefings = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == BRIEFING
    ]
    assert len(briefings) == 1
    assert "[Handoff from alpha]" in briefings[0].content
    assert "SUM[" in briefings[0].content


def test_full_flag_passes_transcript_without_summarizing():
    def exploding(prompt: str, transcript: str) -> str:
        raise AssertionError("must not summarize on full")

    update = build_handoff_update(
        _base_state(),
        "beta",
        payload_flags={"alpha": "full"},
        summary_prompts={},
        default_agent="alpha",
        summarize=exploding,
    )
    assert "alpha" not in update["agent_summaries"]
    briefings = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == BRIEFING
    ]
    assert len(briefings) == 1
    assert "human: do the task" in briefings[0].content


def test_none_flag_sends_no_payload_but_still_archives():
    def exploding(prompt: str, transcript: str) -> str:
        raise AssertionError("must not summarize on none")

    update = build_handoff_update(
        _base_state(),
        "beta",
        payload_flags={"alpha": "none"},
        summary_prompts={},
        default_agent="alpha",
        summarize=exploding,
    )
    assert len(update["agent_archives"]["alpha"]) == 1
    briefings = [
        m
        for m in update["messages"][1:]
        if m.additional_kwargs.get(HANDOFF_MARKER) == BRIEFING
    ]
    assert briefings == []


def test_inflight_user_message_always_carried():
    for flag in ("summary", "full", "none"):
        update = build_handoff_update(
            _base_state(),
            "beta",
            payload_flags={"alpha": flag},
            summary_prompts={},
            default_agent="alpha",
            summarize=_fake_summarize,
        )
        carried = [
            m
            for m in update["messages"][1:]
            if m.additional_kwargs.get(HANDOFF_MARKER) == CARRIED
        ]
        assert len(carried) == 1, flag
        assert carried[0].content == "do the task"


def test_revisit_restores_lazily_generated_summary():
    calls: list[str] = []

    def tracking_summarize(prompt: str, transcript: str) -> str:
        calls.append(transcript)
        return "beta-memory"

    state = _base_state("alpha")
    state["visit_counter"] = 1
    state["agent_archives"] = {
        "beta": [{"order": 1, "agent": "beta", "messages": [AIMessage(content="beta did X")]}]
    }
    state["agent_summaries"] = {}
    update = build_handoff_update(
        state,
        "beta",
        payload_flags={"alpha": "none", "beta": "none"},
        summary_prompts={},
        default_agent="alpha",
        summarize=tracking_summarize,
    )
    # beta departed with flag none (no summary existed) — generated lazily now
    assert update["agent_summaries"]["beta"] == {"text": "beta-memory", "through": 1}
    resume = [m for m in update["messages"][1:] if "[Resuming as beta]" in str(m.content)]
    assert len(resume) == 1
    assert "beta-memory" in resume[0].content
    assert len(calls) == 1
    assert "beta did X" in calls[0]


def test_state_containers_are_not_mutated():
    state = _base_state("alpha")
    state["agent_archives"] = {"beta": []}
    state["agent_summaries"] = {}
    build_handoff_update(
        state,
        "beta",
        payload_flags={"alpha": "summary"},
        summary_prompts={},
        default_agent="alpha",
        summarize=_fake_summarize,
    )
    assert state["agent_archives"] == {"beta": []}
    assert state["agent_summaries"] == {}
    assert "alpha" not in state["agent_archives"]


def test_default_agent_used_when_agent_name_missing():
    state = {"messages": [HumanMessage(content="hello")]}
    update = build_handoff_update(
        state,
        "beta",
        payload_flags={},
        summary_prompts={},
        default_agent="alpha",
        summarize=_fake_summarize,
    )
    assert "alpha" in update["agent_archives"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_service.py -v --no-cov`
Expected: new tests FAIL with `ImportError: cannot import name 'build_handoff_update'`; Task 3 tests still pass.

- [ ] **Step 3: Implement build_handoff_update**

First extend the imports at the top of `src/autobots_devtools_shared_lib/dynagent/services/history.py`: add `Mapping` to the `collections.abc` import, add `from typing import Any`, add `RemoveMessage` to the `langchain.messages` import, and add `from langgraph.graph.message import REMOVE_ALL_MESSAGES`. Then append:

```python
def build_handoff_update(
    state: Mapping[str, Any],
    next_agent: str,
    *,
    payload_flags: Mapping[str, str],
    summary_prompts: Mapping[str, str | None],
    default_agent: str,
    summarize: Summarize,
) -> dict[str, Any]:
    """Compute the full Command update for an isolated-mode handoff.

    Archives the departing agent's Live Slice as a new Visit, maintains lazy
    rolling summaries, and assembles the arriving agent's fresh context:
    RemoveMessage(all) + optional resume briefing + optional payload briefing
    + carried In-flight User Message.

    Known limitation (documented, by design): handoff must be the only tool
    call in its AI turn — a sibling tool's ToolMessage landing after the wipe
    would be orphaned in the fresh context.
    """
    live: list[AnyMessage] = list(state.get("messages") or [])
    departing: str = state.get("agent_name") or default_agent
    order = int(state.get("visit_counter") or 0) + 1

    archives: dict[str, list[Visit]] = {
        name: list(visits) for name, visits in (state.get("agent_archives") or {}).items()
    }
    summaries: dict[str, AgentSummary] = dict(state.get("agent_summaries") or {})

    visit: Visit = {"order": order, "agent": departing, "messages": live}
    archives.setdefault(departing, []).append(visit)

    flag = payload_flags.get(departing, "summary")
    departing_prompt = summary_prompts.get(departing) or DEFAULT_SUMMARY_PROMPT
    arriving_prompt = summary_prompts.get(next_agent) or DEFAULT_SUMMARY_PROMPT

    if flag == "summary":
        summaries[departing] = roll_summary(
            summaries.get(departing), archives[departing], departing_prompt, summarize
        )

    fresh: list[AnyMessage] = [RemoveMessage(id=REMOVE_ALL_MESSAGES)]

    arriving_visits = archives.get(next_agent, [])
    if arriving_visits:
        summaries[next_agent] = roll_summary(
            summaries.get(next_agent), arriving_visits, arriving_prompt, summarize
        )
        fresh.append(
            HumanMessage(
                content=(
                    f"[Resuming as {next_agent}] Summary of your previous work:\n"
                    f"{summaries[next_agent]['text']}"
                ),
                additional_kwargs={HANDOFF_MARKER: BRIEFING},
            )
        )

    # Self-handoff: the resume briefing already covers the payload.
    if next_agent != departing:
        if flag == "summary":
            payload_text = summaries[departing]["text"]
        elif flag == "full":
            payload_text = render_transcript(live)
        else:
            payload_text = ""
        if payload_text:
            fresh.append(
                HumanMessage(
                    content=f"[Handoff from {departing}]\n{payload_text}",
                    additional_kwargs={HANDOFF_MARKER: BRIEFING},
                )
            )

    inflight = find_inflight_user_message(live)
    if inflight is not None:
        fresh.append(
            HumanMessage(
                content=inflight.content,
                additional_kwargs={HANDOFF_MARKER: CARRIED},
            )
        )

    logger.info(
        f"Isolated handoff: {departing} -> {next_agent} "
        f"(visit {order}, payload={flag}, revisit={bool(arriving_visits)})"
    )
    return {
        "messages": fresh,
        "agent_name": next_agent,
        "agent_archives": archives,
        "agent_summaries": summaries,
        "visit_counter": order,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_service.py -v --no-cov`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/services/history.py tests/unit/test_history_service.py
git commit -m "feat: build_handoff_update — archive, lazy summaries, fresh context

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Wire the handoff tool + get_my_history tool

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/services/history.py` (add `summarize_with_lm`, `render_my_history`)
- Modify: `src/autobots_devtools_shared_lib/dynagent/tools/state_tools.py`
- Modify: `src/autobots_devtools_shared_lib/dynagent/tools/tool_registry.py`
- Test: `tests/unit/test_state_tools.py`, `tests/unit/test_tool_registry.py`

**Interfaces:**
- Consumes: `build_handoff_update`, `render_transcript`, `AgentMeta` (Task 2 fields: `history_mode`, `handoff_payload_map`, `summary_prompt_map`, `default_agent`), `lm()`.
- Produces:
  - `summarize_with_lm(prompt_text: str, transcript_text: str) -> str` in `services/history.py` (the production `Summarize`; sync, so it works in both sync and async engines)
  - `render_my_history(state: Mapping[str, Any]) -> str` in `services/history.py`
  - `perform_handoff(state: Mapping[str, Any], next_agent: str, tool_call_id: str) -> Command` in `state_tools.py` (the `handoff` tool delegates to it; tests call it directly)
  - `@tool get_my_history` in `state_tools.py`, registered in `get_default_tools()` — agents opt in by listing `get_my_history` in their `tools:`.

- [ ] **Step 1: Write the failing tests**

First merge these into the **top import block** of `tests/unit/test_state_tools.py` (never mid-file — ruff E402):

```python
import pytest
from langchain.messages import AIMessage, HumanMessage, RemoveMessage

from autobots_devtools_shared_lib.dynagent.agents import agent_config_utils
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.services import history as history_service
from autobots_devtools_shared_lib.dynagent.services.history import render_my_history
from autobots_devtools_shared_lib.dynagent.tools.state_tools import perform_handoff
```

Then append the tests:

```python
# --- Isolated-mode handoff (perform_handoff) ---


@pytest.fixture
def isolated_meta(monkeypatch):
    """Install a stub AgentMeta in isolated mode with agents alpha/beta."""
    meta = AgentMeta.__new__(AgentMeta)
    meta.history_mode = "isolated"
    meta.handoff_payload_map = {"alpha": "summary", "beta": "none"}
    meta.summary_prompt_map = {"alpha": None, "beta": None}
    meta.default_agent = "alpha"
    monkeypatch.setattr(AgentMeta, "_instance", meta)
    monkeypatch.setattr(agent_config_utils, "get_agent_list", lambda: ["alpha", "beta"])
    monkeypatch.setattr(
        history_service, "summarize_with_lm", lambda prompt, transcript: "STUBBED SUMMARY"
    )
    yield meta
    AgentMeta.reset()


@pytest.fixture
def shared_meta(monkeypatch):
    """Install a stub AgentMeta in shared (legacy) mode."""
    meta = AgentMeta.__new__(AgentMeta)
    meta.history_mode = "shared"
    meta.handoff_payload_map = {}
    meta.summary_prompt_map = {}
    meta.default_agent = "alpha"
    monkeypatch.setattr(AgentMeta, "_instance", meta)
    monkeypatch.setattr(agent_config_utils, "get_agent_list", lambda: ["alpha", "beta"])
    yield meta
    AgentMeta.reset()


def _live_state() -> dict:
    return {
        "agent_name": "alpha",
        "messages": [HumanMessage(content="please do X"), AIMessage(content="doing X")],
    }


def test_perform_handoff_shared_mode_unchanged(shared_meta):
    result = perform_handoff(_live_state(), "beta", "tc-1")
    assert result.update is not None
    assert result.update["agent_name"] == "beta"
    # legacy shape: a single ToolMessage, no wipe, no archives
    assert "agent_archives" not in result.update
    assert len(result.update["messages"]) == 1
    assert result.update["messages"][0].tool_call_id == "tc-1"


def test_perform_handoff_isolated_wipes_and_archives(isolated_meta):
    result = perform_handoff(_live_state(), "beta", "tc-2")
    assert result.update is not None
    assert result.update["agent_name"] == "beta"
    assert isinstance(result.update["messages"][0], RemoveMessage)
    assert len(result.update["agent_archives"]["alpha"]) == 1
    assert result.update["agent_summaries"]["alpha"]["text"] == "STUBBED SUMMARY"


def test_perform_handoff_isolated_invalid_agent_still_errors(isolated_meta):
    result = perform_handoff(_live_state(), "nope", "tc-3")
    assert result.update is not None
    assert "agent_name" not in result.update
    assert "Invalid agent" in result.update["messages"][0].content


# --- render_my_history ---


def test_render_my_history_empty():
    state = {"agent_name": "alpha"}
    assert "No archived history" in render_my_history(state)


def test_render_my_history_renders_visits_in_order():
    state = {
        "agent_name": "alpha",
        "agent_archives": {
            "alpha": [
                {"order": 1, "agent": "alpha", "messages": [AIMessage(content="first pass")]},
                {"order": 4, "agent": "alpha", "messages": [AIMessage(content="second pass")]},
            ],
            "beta": [{"order": 2, "agent": "beta", "messages": [AIMessage(content="beta work")]}],
        },
    }
    text = render_my_history(state)
    assert "Visit 1" in text
    assert "first pass" in text
    assert "second pass" in text
    assert "beta work" not in text
    assert text.index("first pass") < text.index("second pass")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_state_tools.py -v --no-cov`
Expected: new tests FAIL with `ImportError: cannot import name 'render_my_history'` (or `perform_handoff`); existing tests pass.

- [ ] **Step 3: Implement**

3a. Append to `src/autobots_devtools_shared_lib/dynagent/services/history.py`:

```python
def summarize_with_lm(prompt_text: str, transcript_text: str) -> str:
    """Production Summarize: one sync LLM call (sync works in both engine modes)."""
    from autobots_devtools_shared_lib.dynagent.llm.llm import lm

    response = lm().invoke([HumanMessage(content=f"{prompt_text}\n\n{transcript_text}")])
    return response.text or ""


def render_my_history(state: Mapping[str, Any]) -> str:
    """Render the current agent's own archived Visits as readable text."""
    agent = state.get("agent_name") or ""
    visits: Sequence[Visit] = (state.get("agent_archives") or {}).get(agent, [])
    if not visits:
        return "No archived history for this agent."
    parts = [
        f"--- Visit {visit['order']} ---\n{render_transcript(visit['messages'])}"
        for visit in visits
    ]
    return "\n\n".join(parts)
```

3b. In `src/autobots_devtools_shared_lib/dynagent/tools/state_tools.py`, replace the existing `handoff` tool with (and keep `error_cmd` / `transition_cmd` / `_validate_handoff` / `get_agent_list` untouched):

```python
def perform_handoff(state: Mapping[str, Any], next_agent: str, tool_call_id: str) -> Command:
    """Handoff implementation shared by the tool wrapper — branches on history mode.

    In isolated mode the update wipes `messages` and never appends a
    ToolMessage: the AIMessage holding the pending tool call is wiped too, so
    no dangling pair reaches the provider. Consequence: handoff must be the
    only tool call in its AI turn (sibling ToolMessages would be orphaned).
    """
    error = _validate_handoff(next_agent)
    if error:
        return error_cmd(error, tool_call_id)

    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
    from autobots_devtools_shared_lib.dynagent.services import history as history_service

    meta = AgentMeta.instance()
    if meta.history_mode == "isolated":
        update = history_service.build_handoff_update(
            state,
            next_agent,
            payload_flags=meta.handoff_payload_map,
            summary_prompts=meta.summary_prompt_map,
            default_agent=meta.default_agent or "coordinator",
            summarize=history_service.summarize_with_lm,
        )
        return Command(update=update)

    logger.info(f"Handoff to {next_agent}")
    return transition_cmd(f"Handoff to {next_agent}", tool_call_id, next_agent)


@tool
def handoff(runtime: ToolRuntime[None, Dynagent], next_agent: str) -> Command:
    """Transition to a different agent."""
    return perform_handoff(runtime.state, next_agent, runtime.tool_call_id or "unknown")


@tool
def get_my_history(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Return the transcript of your own archived previous visits in this session."""
    from autobots_devtools_shared_lib.dynagent.services.history import render_my_history

    return render_my_history(runtime.state)
```

Add `from collections.abc import Mapping` to the imports at the top of `state_tools.py`. Note `history_service.summarize_with_lm` is deliberately resolved through the module attribute so tests can monkeypatch `history_service.summarize_with_lm`.

3c. In `src/autobots_devtools_shared_lib/dynagent/tools/tool_registry.py`: extend the `state_tools` import and `get_default_tools()`:

```python
from autobots_devtools_shared_lib.dynagent.tools.state_tools import (
    get_agent_list,
    get_my_history,
    handoff,
)
```

and add `get_my_history,` to the returned list in `get_default_tools()` right after `get_agent_list,`.

3d. Append to `tests/unit/test_tool_registry.py`:

```python
def test_default_tools_include_get_my_history():
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_default_tools

    names = {t.name for t in get_default_tools()}
    assert "get_my_history" in names
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_state_tools.py tests/unit/test_tool_registry.py -v --no-cov`
Expected: PASS (all).

- [ ] **Step 5: Run the whole unit suite to catch regressions**

Run: `../.venv/bin/pytest tests/unit -x -q --no-cov`
Expected: PASS. (`test_public_api.py` and `test_base_agent_factory.py` exercise the unchanged shared path.)

- [ ] **Step 6: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/services/history.py src/autobots_devtools_shared_lib/dynagent/tools/state_tools.py src/autobots_devtools_shared_lib/dynagent/tools/tool_registry.py tests/unit/test_state_tools.py tests/unit/test_tool_registry.py
git commit -m "feat: wire isolated handoff into handoff tool; add get_my_history tool

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Transcript reassembly + public export + wipe-semantics proof

**Files:**
- Modify: `src/autobots_devtools_shared_lib/dynagent/services/history.py`
- Modify: `src/autobots_devtools_shared_lib/dynagent/__init__.py`
- Test: `tests/unit/test_history_service.py`

**Interfaces:**
- Consumes: `Visit`, `HANDOFF_MARKER`.
- Produces: `reassemble_transcript(state: Mapping[str, Any]) -> list[AnyMessage]`, exported from `autobots_devtools_shared_lib.dynagent`. Synthetic messages (any `HANDOFF_MARKER` in `additional_kwargs`) are excluded — briefings are noise and carried copies are duplicates of originals in earlier Visits.

- [ ] **Step 1: Write the failing tests**

First merge these into the **top import block** of `tests/unit/test_history_service.py` (never mid-file — ruff E402): extend the `langgraph.graph.message` import with `add_messages`, and the `history` import with `reassemble_transcript`.

Then append the tests:

```python
# --- reassemble_transcript ---


def test_reassemble_orders_visits_globally_and_appends_live():
    state = {
        "agent_archives": {
            "beta": [{"order": 2, "agent": "beta", "messages": [AIMessage(content="beta work")]}],
            "alpha": [
                {"order": 1, "agent": "alpha", "messages": [HumanMessage(content="start")]}
            ],
        },
        "messages": [AIMessage(content="live now")],
    }
    transcript = reassemble_transcript(state)
    contents = [m.content for m in transcript]
    assert contents == ["start", "beta work", "live now"]


def test_reassemble_filters_synthetic_messages():
    state = {
        "agent_archives": {},
        "messages": [
            HumanMessage(content="briefing", additional_kwargs={HANDOFF_MARKER: BRIEFING}),
            HumanMessage(content="carried", additional_kwargs={HANDOFF_MARKER: CARRIED}),
            HumanMessage(content="real"),
        ],
    }
    contents = [m.content for m in reassemble_transcript(state)]
    assert contents == ["real"]


def test_reassemble_empty_state():
    assert reassemble_transcript({}) == []


# --- wipe semantics through the real add_messages reducer ---


def test_handoff_update_wipes_via_add_messages_reducer():
    existing = [
        HumanMessage(content="please do X", id="m1"),
        AIMessage(content="doing X", id="m2"),
    ]
    update = build_handoff_update(
        {"agent_name": "alpha", "messages": existing},
        "beta",
        payload_flags={"alpha": "none"},
        summary_prompts={},
        default_agent="alpha",
        summarize=_fake_summarize,
    )
    merged = add_messages(existing, update["messages"])
    # old ids are gone; only the carried copy remains
    assert [m.content for m in merged] == ["please do X"]
    assert all(m.id not in {"m1", "m2"} for m in merged)


def test_public_api_exports_reassemble_transcript():
    from autobots_devtools_shared_lib.dynagent import reassemble_transcript as exported

    assert exported is reassemble_transcript
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../.venv/bin/pytest tests/unit/test_history_service.py -v --no-cov`
Expected: new tests FAIL with `ImportError: cannot import name 'reassemble_transcript'`.

- [ ] **Step 3: Implement**

3a. Append to `src/autobots_devtools_shared_lib/dynagent/services/history.py`:

```python
def reassemble_transcript(state: Mapping[str, Any]) -> list[AnyMessage]:
    """Reassemble the user-facing Transcript from archives plus the Live Slice.

    In isolated mode `state['messages']` is only the current agent's working
    slice — UIs and resume paths must call this instead of reading it raw.
    Synthetic handoff messages are excluded: briefings are engine noise and
    carried copies duplicate originals already present in earlier Visits.
    """
    visits: list[Visit] = []
    for agent_visits in (state.get("agent_archives") or {}).values():
        visits.extend(agent_visits)
    visits.sort(key=lambda visit: visit["order"])

    transcript: list[AnyMessage] = []
    for visit in visits:
        transcript.extend(
            msg for msg in visit["messages"] if HANDOFF_MARKER not in msg.additional_kwargs
        )
    transcript.extend(
        msg for msg in (state.get("messages") or []) if HANDOFF_MARKER not in msg.additional_kwargs
    )
    return transcript
```

3b. In `src/autobots_devtools_shared_lib/dynagent/__init__.py`: add the import (alphabetical with the others):

```python
from autobots_devtools_shared_lib.dynagent.services.history import reassemble_transcript
```

and add `"reassemble_transcript",` to `__all__` (keep it sorted).

- [ ] **Step 4: Run tests to verify they pass**

Run: `../.venv/bin/pytest tests/unit/test_history_service.py tests/unit/test_public_api.py -v --no-cov`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/services/history.py src/autobots_devtools_shared_lib/dynagent/__init__.py tests/unit/test_history_service.py
git commit -m "feat: reassemble_transcript helper + public export

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Documentation + full verification

**Files:**
- Create: `docs/features/isolated-history.md`
- Modify: none (verification only)

- [ ] **Step 1: Write the feature doc**

Create `docs/features/isolated-history.md`:

```markdown
# Isolated History Mode

Per-agent message history for the classic engine. Design rationale:
[ADR 0001](../adr/0001-isolated-history-mode.md). Vocabulary: [CONTEXT.md](../../CONTEXT.md).

## Enabling

```yaml
# agents.yaml
history_mode: isolated   # default: shared (legacy behavior, unchanged)

agents:
  coordinator:
    prompt: coordinator
    tools: [handoff, get_agent_list]
    handoff_payload: none        # summary (default) | full | none
  extractor:
    prompt: extractor
    tools: [handoff, get_my_history]
    handoff_payload: summary
    summary_prompt: extractor-summary   # optional -> prompts/extractor-summary.md
```

## Semantics

| Concern | Behavior |
|---|---|
| On handoff | Departing agent's live slice is archived as a Visit; arriving agent starts fresh |
| Arriving context | Optional resume briefing (own rolling summary, revisits only) + optional payload briefing (per departing agent's `handoff_payload`) + the in-flight user message (always) |
| Task facts | Travel via the context store / prompt injection — never via messages |
| Summaries | Lazy + rolling: generated only when a handoff needs one; each update folds in only uncovered visits |
| Retrieval | `get_my_history` tool (opt-in per agent) returns the agent's own archived visits; agents can never read another agent's raw history |
| Transcript | `from autobots_devtools_shared_lib.dynagent import reassemble_transcript` — `state["messages"]` is no longer the conversation |

## Constraints

- `handoff` must be the only tool call in its AI turn (the wipe would orphan sibling ToolMessages).
- The global `SummarizationMiddleware` still runs; if it compacts mid-visit, the archive holds the compacted slice.
- Classic engine only; the deep engine isolates subagent contexts by construction.
```

- [ ] **Step 2: Run the full check suite**

```bash
make check-format && make type-check && make test
```

Expected: ruff format --check clean, ruff check clean, pyright clean, all tests pass. Fix anything that surfaces (formatting drift is likely — run `make format` and re-check).

- [ ] **Step 3: Commit**

```bash
git add docs/features/isolated-history.md
git commit -m "docs: isolated history mode feature guide

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Final verification of the branch**

```bash
git log --oneline main..HEAD
```

Expected: 7 commits (branch task produces none), each scoped as above. Do not merge or push — integration is decided by the user (superpowers:finishing-a-development-branch).
