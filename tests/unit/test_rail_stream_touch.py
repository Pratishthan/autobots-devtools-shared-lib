# ABOUTME: Tests project_stream's touch-on-finish hook and best-effort projection guard.
# ABOUTME: A raising projection must not break passthrough; RUN_FINISHED triggers touch.

from unittest.mock import patch

import pytest


async def _aiter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_calls_on_run_finished_with_thread_id():
    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import project_stream

    touched: list[str] = []

    async def on_finish(thread_id: str) -> None:
        touched.append(thread_id)

    events = [
        {"type": "RUN_STARTED", "thread_id": "abc", "_t_ms": 0},
        {"type": "RUN_FINISHED", "thread_id": "abc", "_t_ms": 5},
    ]
    out = [ev async for ev in project_stream(_aiter(events), set(), on_run_finished=on_finish)]

    passthrough = [ev for ev in out if isinstance(ev, dict)]
    assert passthrough == events
    assert touched == ["abc"]


@pytest.mark.asyncio
async def test_projection_error_drops_delta_not_stream():
    from autobots_devtools_shared_lib.dynagent.ui import rail_stream

    events = [{"type": "RUN_STARTED", "thread_id": "z", "_t_ms": 0}]

    with patch.object(rail_stream.ActivityProjection, "observe", side_effect=RuntimeError("boom")):
        out = [ev async for ev in rail_stream.project_stream(_aiter(events), set())]

    # the token/event stream survives even though projection blew up
    assert [ev for ev in out if isinstance(ev, dict)] == events
