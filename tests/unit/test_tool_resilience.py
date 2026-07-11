# ABOUTME: Unit tests for ToolResilienceMiddleware.
# ABOUTME: Tool exceptions become error ToolMessages; CancelledError propagates.

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from autobots_devtools_shared_lib.dynagent.middleware.tool_resilience import (
    ToolResilienceMiddleware,
)


def _request():
    return SimpleNamespace(tool_call={"name": "my_tool", "id": "call-1", "args": {}})


def test_success_passes_through():
    mw = ToolResilienceMiddleware()
    ok = ToolMessage(content="fine", tool_call_id="call-1")
    assert mw.wrap_tool_call(_request(), lambda _req: ok) is ok  # type: ignore


def test_exception_becomes_error_tool_message():
    mw = ToolResilienceMiddleware()

    def boom(_req):
        raise RuntimeError("sidecar unreachable")

    msg = mw.wrap_tool_call(_request(), boom)  # type: ignore
    assert isinstance(msg, ToolMessage)
    assert msg.status == "error"
    assert msg.tool_call_id == "call-1"
    assert "my_tool" in msg.content
    assert "sidecar unreachable" in msg.content


def test_error_summary_is_truncated():
    mw = ToolResilienceMiddleware()

    def boom(_req):
        raise RuntimeError("x" * 5000)

    msg = mw.wrap_tool_call(_request(), boom)  # type: ignore
    assert len(msg.content) < 1000


def test_cancelled_error_is_reraised():
    mw = ToolResilienceMiddleware()

    def cancel(_req):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        mw.wrap_tool_call(_request(), cancel)  # type: ignore


async def test_async_exception_becomes_error_tool_message():
    mw = ToolResilienceMiddleware()

    async def boom(_req):
        raise ValueError("bad input")

    msg = await mw.awrap_tool_call(_request(), boom)  # type: ignore
    assert msg.status == "error"
    assert "bad input" in msg.content


async def test_async_cancelled_error_is_reraised():
    mw = ToolResilienceMiddleware()

    async def cancel(_req):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await mw.awrap_tool_call(_request(), cancel)  # type: ignore
