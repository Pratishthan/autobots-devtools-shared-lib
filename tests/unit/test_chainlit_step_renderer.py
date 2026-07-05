# ABOUTME: Routing tests for ChainlitStepRenderer using fake cl.Message/cl.Step objects.
# ABOUTME: Verifies main-vs-subagent token routing, nested-tool parenting, eviction, collapse.

import pytest

from autobots_devtools_shared_lib.dynagent.ui import ui_utils


class FakeMessage:
    def __init__(self, content=""):
        self.content = content
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


async def test_main_tokens_go_to_message_subagent_tokens_go_to_step(patched):
    r = ui_utils.ChainlitStepRenderer(on_structured_output=None)
    await r.start()
    # main agent establishes itself first (its chat-model event sets main_agent)
    await r.dispatch(_stream("assistant", "m", "Hi "))
    await r.dispatch(_stream("weather_expert", "w", "sunny"))
    assert r.msg.tokens == ["Hi "]
    step = r._agent_steps["weather_expert"]
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
    subagent_step = r._agent_steps["weather_expert"]
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
    step = r._agent_steps["weather_expert"]
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
    step = r._agent_steps["math_expert"]
    await r.finish()
    assert step.default_open is False
    assert r.msg.updated >= 1
