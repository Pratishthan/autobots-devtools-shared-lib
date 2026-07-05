# ABOUTME: Unit tests for the deep-engine system-message-collapse middleware.
# ABOUTME: Verifies it merges (not strips) all SystemMessages into one leading block.

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.messages import HumanMessage, SystemMessage


class _Req:
    """Minimal stand-in for the middleware ModelRequest surface used by the shim."""

    def __init__(self, system_message, messages):
        self.system_message = system_message
        self.messages = messages
        self.overrides = None

    def override(self, **kwargs):
        self.overrides = kwargs
        return kwargs


@pytest.mark.asyncio
async def test_merges_dedicated_and_inline_system_messages():
    from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
        collapse_system_messages,
    )

    req = _Req(
        system_message=SystemMessage(content="BASE PROMPT"),
        messages=[
            SystemMessage(content="App Context: {thread_id: 1}"),
            HumanMessage(content="hi"),
        ],
    )
    handler = AsyncMock(return_value="ok")

    result = await collapse_system_messages.awrap_model_call(req, handler)

    assert result == "ok"
    passed = handler.await_args.args[0]  # the overridden request kwargs dict
    # inline SystemMessages removed from messages, only Human remains
    assert all(not isinstance(m, SystemMessage) for m in passed["messages"])
    assert len(passed["messages"]) == 1
    # dedicated + inline merged, in order, into one leading system block
    assert passed["system_message"].content == "BASE PROMPT\n\nApp Context: {thread_id: 1}"


@pytest.mark.asyncio
async def test_noop_when_single_system_message():
    from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
        collapse_system_messages,
    )

    req = _Req(system_message=SystemMessage(content="ONLY"), messages=[HumanMessage(content="hi")])
    handler = AsyncMock(return_value="ok")

    await collapse_system_messages.awrap_model_call(req, handler)

    passed = handler.await_args.args[0]
    assert passed["system_message"].content == "ONLY"
    assert passed["messages"] == [req.messages[0]]


def test_sync_merges_dedicated_and_inline_system_messages():
    from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
        collapse_system_messages_sync,
    )

    req = _Req(
        system_message=SystemMessage(content="BASE PROMPT"),
        messages=[
            SystemMessage(content="App Context: {thread_id: 1}"),
            HumanMessage(content="hi"),
        ],
    )
    handler = MagicMock(return_value="ok")

    result = collapse_system_messages_sync.wrap_model_call(req, handler)

    assert result == "ok"
    passed = handler.call_args.args[0]  # the overridden request kwargs dict
    # inline SystemMessages removed from messages, only Human remains
    assert all(not isinstance(m, SystemMessage) for m in passed["messages"])
    assert len(passed["messages"]) == 1
    # dedicated + inline merged, in order, into one leading system block
    assert passed["system_message"].content == "BASE PROMPT\n\nApp Context: {thread_id: 1}"


def test_sync_noop_when_single_system_message():
    from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
        collapse_system_messages_sync,
    )

    req = _Req(system_message=SystemMessage(content="ONLY"), messages=[HumanMessage(content="hi")])
    handler = MagicMock(return_value="ok")

    collapse_system_messages_sync.wrap_model_call(req, handler)

    passed = handler.call_args.args[0]
    assert passed["system_message"].content == "ONLY"
    assert passed["messages"] == [req.messages[0]]
