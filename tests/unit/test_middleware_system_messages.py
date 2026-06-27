# ABOUTME: Unit tests for system-message handling in the inject_agent middleware.
# ABOUTME: Guards against the "multiple non-consecutive system messages" Anthropic error.

import pytest
from langchain.agents.middleware import ModelRequest
from langchain.messages import AIMessage, HumanMessage, SystemMessage

from autobots_devtools_shared_lib.dynagent.agents import middleware
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta


class _FakeMeta:
    """Minimal stand-in for AgentMeta with a single agent."""

    default_agent = "coordinator"
    prompt_map = {"coordinator": "You are the coordinator."}
    tool_map = {"coordinator": []}
    input_schema_map: dict = {}
    output_schema_map: dict = {}


@pytest.fixture
def fake_meta(monkeypatch):
    monkeypatch.setattr(AgentMeta, "instance", classmethod(lambda cls: _FakeMeta()))
    yield


def _make_request(messages):
    # model is never invoked by the middleware itself, so a placeholder is fine.
    return ModelRequest(model=object(), messages=messages, state={"messages": messages})


async def test_strips_leaked_system_message_from_messages(fake_meta):
    """A SystemMessage leaked into the message list (e.g. CopilotKit instructions)
    must be removed so the injected prompt is the only system message."""
    leaked = SystemMessage(content="Frontend instructions")
    user = HumanMessage(content="Hello")
    request = _make_request([leaked, user])

    captured: dict = {}

    async def handler(req):
        captured["req"] = req
        return "ok"

    result = await middleware.inject_agent_async.awrap_model_call(request, handler)

    assert result == "ok"
    out = captured["req"]
    # Exactly one system message, carried in the dedicated field — none left in the list.
    assert all(not isinstance(m, SystemMessage) for m in out.messages)
    assert out.system_message is not None
    assert out.system_message.content == "You are the coordinator."


async def test_preserves_non_system_messages(fake_meta):
    """Stripping system messages must not drop conversational turns."""
    msgs = [
        SystemMessage(content="leaked"),
        HumanMessage(content="hi"),
        AIMessage(content="hello"),
        HumanMessage(content="bye"),
    ]
    request = _make_request(msgs)

    captured: dict = {}

    async def handler(req):
        captured["req"] = req
        return "ok"

    await middleware.inject_agent_async.awrap_model_call(request, handler)

    out_contents = [m.content for m in captured["req"].messages]
    assert out_contents == ["hi", "hello", "bye"]
