# ABOUTME: Routing tests for ChainlitStepRenderer using fake cl.Message/cl.Step objects.
# ABOUTME: Verifies main-vs-subagent token routing, nested-tool parenting, eviction, collapse.

import pytest

from autobots_devtools_shared_lib.dynagent.ui import ui_utils


class FakeMessage:
    def __init__(self, content="", author=None):
        self.content = content
        self.author = author
        self.tokens: list[str] = []
        self.sent = False
        self.updated = 0

    async def send(self):
        self.sent = True
        return self

    async def update(self):
        self.updated += 1

    async def stream_token(self, token):
        self.tokens.append(token)
        self.content += token


class FakeStep:
    _n = 0

    def __init__(
        self, name=None, type=None, id=None, parent_id=None, default_open=False, auto_collapse=False
    ):
        FakeStep._n += 1
        self.id = id or f"step-{FakeStep._n}"
        self.name = name
        self.type = type
        self.parent_id = parent_id
        self.default_open = default_open
        self.auto_collapse = auto_collapse
        self.input = None
        self.output = None
        self.tokens: list[str] = []
        self.sent = False
        self.updated = 0
        self.removed = False

    async def send(self):
        self.sent = True
        return self

    async def update(self):
        self.updated += 1

    async def remove(self):
        self.removed = True

    async def stream_token(self, token):
        self.tokens.append(token)


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(ui_utils.cl, "Message", FakeMessage)
    monkeypatch.setattr(ui_utils.cl, "Step", FakeStep)


def _stream(agent: str, run_id: str, text: str) -> dict:
    class _C:
        content = text

    return {
        "event": "on_chat_model_stream",
        "run_id": run_id,
        "metadata": {"lc_agent_name": agent},
        "data": {"chunk": _C()},
    }


def _tool_start(agent: str, run_id: str, name: str, tool_input: dict) -> dict:
    return {
        "event": "on_tool_start",
        "run_id": run_id,
        "name": name,
        "metadata": {"lc_agent_name": agent},
        "data": {"input": tool_input},
    }


def _tool_end(run_id: str, output: str) -> dict:
    return {"event": "on_tool_end", "run_id": run_id, "data": {"output": output}}


def _chain_end(run_id: str, output: dict) -> dict:
    return {"event": "on_chain_end", "run_id": run_id, "data": {"output": output}}


async def test_main_tokens_go_to_message_subagent_tokens_go_to_step(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    # main agent establishes itself first (its chat-model event sets main_agent)
    await r.dispatch(_stream("assistant", "m", "Hi "))
    await r.dispatch(_stream("weather_expert", "w", "sunny"))
    assert r.msg.tokens == ["Hi "]
    step = r._subagent_steps["weather_expert"]
    assert step.tokens == ["sunny"]
    assert step.name == "🧵 weather_expert"
    assert step.default_open is True
    assert step.parent_id is None


async def test_nested_tool_parents_under_subagent_step(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_stream("weather_expert", "w", "..."))  # creates the subagent step
    await r.dispatch(
        _tool_start("weather_expert", "t-weather", "spike_tools__get_weather", {"city": "Paris"})
    )
    subagent_step = r._subagent_steps["weather_expert"]
    tool_step = r._tool_steps["t-weather"]
    assert tool_step.parent_id == subagent_step.id


async def test_main_tool_is_top_level(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_tool_start("assistant", "t1", "spike_tools__get_secret_number", {}))
    assert r._tool_steps["t1"].parent_id is None


async def test_task_dispatch_creates_no_tool_step(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(
        _tool_start("assistant", "t-task", "task", {"subagent_type": "weather_expert"})
    )
    assert "t-task" not in r._tool_steps


async def test_main_tool_eviction_removes_oldest_beyond_three(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_tool_start("assistant", "tool-0", "spike_tools__t0", {}))
    evicted_step = r._tool_steps["tool-0"]
    for i in range(1, 4):
        await r.dispatch(_tool_start("assistant", f"tool-{i}", f"spike_tools__t{i}", {}))
    assert evicted_step.removed is True
    assert "tool-0" not in r._tool_steps
    assert set(r._tool_steps) == {"tool-1", "tool-2", "tool-3"}


async def test_subagent_tool_steps_are_never_evicted(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_stream("weather_expert", "w", "..."))  # creates the subagent step
    for i in range(5):
        await r.dispatch(_tool_start("weather_expert", f"sub-tool-{i}", f"spike_tools__t{i}", {}))
    for i in range(5):
        run_id = f"sub-tool-{i}"
        assert run_id in r._tool_steps
        assert r._tool_steps[run_id].removed is False


async def test_subagent_step_collapses_on_task_end(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_stream("weather_expert", "w", "sunny"))
    await r.dispatch(
        _tool_start("assistant", "t-task", "task", {"subagent_type": "weather_expert"})
    )
    step = r._subagent_steps["weather_expert"]
    await r.dispatch(_tool_end("t-task", "done"))
    assert step.default_open is False
    assert step.updated >= 1


async def test_tool_end_records_output(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_tool_start("assistant", "t1", "spike_tools__get_secret_number", {}))
    await r.dispatch(_tool_end("t1", "42"))
    assert r._tool_steps["t1"].output == "42"


async def test_finish_collapses_open_subagent_steps(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_stream("math_expert", "n", "51"))  # never receives a task-end
    step = r._subagent_steps["math_expert"]
    await r.finish()
    assert step.default_open is False
    assert r.msg.updated >= 1


async def test_chain_end_structured_output_not_suppressed_when_owner_is_main(patched):
    # Classic single-graph domain: the main agent's lc_agent_name ("assistant") is
    # established via a token stream on run_id "m". The chain-end event for that same
    # run_id carries a structured_response whose Dynagent state `agent_name` field is a
    # *different* string ("data_models"), modeling a post-handoff state mutation. This
    # must still render: ownership is resolved from the event's own lc_agent_name
    # attribution (via the run_id fallback populated by the earlier token event), not
    # from the unrelated Dynagent state field.
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    event = _chain_end("m", {"structured_response": {"foo": "bar"}, "agent_name": "data_models"})
    await r.dispatch(event)
    assert r.structured_response_count == 1


async def test_chain_end_structured_output_suppressed_for_subagent(patched):
    # A genuine subagent (distinct lc_agent_name "weather_expert" on its own run_id "w")
    # producing a structured_response must still be suppressed.
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_stream("weather_expert", "w", "..."))
    event = _chain_end("w", {"structured_response": {"foo": "bar"}, "agent_name": "weather_expert"})
    await r.dispatch(event)
    assert r.structured_response_count == 0


def _stream_with_parents(agent, run_id, text, parent_ids):
    class _C:
        content = text

    return {
        "event": "on_chat_model_stream",
        "run_id": run_id,
        "parent_ids": parent_ids,
        "metadata": {"lc_agent_name": agent},
        "data": {"chunk": _C()},
    }


def _task_dispatch(run_id, subagent_type, description):
    return {
        "event": "on_tool_start",
        "run_id": run_id,
        "name": "task",
        "data": {"input": {"subagent_type": subagent_type, "description": description}},
    }


async def test_same_type_parallel_dispatches_get_separate_steps(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_task_dispatch("d1", "general-purpose", "Research Rust"))
    await r.dispatch(_task_dispatch("d2", "general-purpose", "Research Kotlin"))
    await r.dispatch(_stream_with_parents("general-purpose", "mA", "rust text", ["d1"]))
    await r.dispatch(_stream_with_parents("general-purpose", "mB", "kotlin text", ["d2"]))

    step1 = r._subagent_steps["d1"]
    step2 = r._subagent_steps["d2"]
    assert step1 is not step2
    assert step1.tokens == ["rust text"]
    assert step2.tokens == ["kotlin text"]
    assert step1.name == "🧵 general-purpose · Research Rust"
    assert step2.name == "🧵 general-purpose · Research Kotlin"


async def test_dispatch_step_collapses_on_its_task_end(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_task_dispatch("d1", "general-purpose", "Research Rust"))
    await r.dispatch(_stream_with_parents("general-purpose", "mA", "rust", ["d1"]))
    step = r._subagent_steps["d1"]
    await r.dispatch(_tool_end("d1", "done"))
    assert step.default_open is False
    assert step.updated >= 1


async def test_nested_tool_parents_under_dispatch_step(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    await r.dispatch(_stream("assistant", "m", "hi"))
    await r.dispatch(_task_dispatch("d1", "general-purpose", "Research Rust"))
    await r.dispatch(_stream_with_parents("general-purpose", "mA", "rust", ["d1"]))
    nested = {
        "event": "on_tool_start",
        "run_id": "nested-1",
        "name": "spike_tools__ls",
        "parent_ids": ["d1", "mA"],
        "metadata": {"lc_agent_name": "general-purpose"},
        "data": {"input": {}},
    }
    await r.dispatch(nested)
    assert r._tool_steps["nested-1"].parent_id == r._subagent_steps["d1"].id
