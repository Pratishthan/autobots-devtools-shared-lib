# ABOUTME: Unit tests for the AG-UI rail streaming wrapper.
# ABOUTME: Verifies project_stream passes events through and interleaves STATE_DELTA.

import pytest


async def _aiter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_passes_events_through_and_injects_state_delta():
    from ag_ui.core import EventType

    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import project_stream

    events = [
        {"type": "RUN_STARTED", "_t_ms": 0},
        {
            "type": "TOOL_CALL_START",
            "tool_call_id": "t1",
            "tool_call_name": "task",
            "parent_message_id": "lc_run--MAIN",
            "_t_ms": 10,
        },
        {
            "type": "TOOL_CALL_ARGS",
            "tool_call_id": "t1",
            "delta": '{"subagent_type": "math_expert"}',
        },
        {"type": "TOOL_CALL_END", "tool_call_id": "t1", "_t_ms": 20},
        {"type": "RUN_FINISHED", "_t_ms": 30},
    ]

    out = [ev async for ev in project_stream(_aiter(events), mcp_servers=set())]

    # every original dict event is preserved, in order
    passthrough = [ev for ev in out if isinstance(ev, dict)]
    assert passthrough == events

    # at least one STATE_DELTA was injected carrying /activity and /stats
    deltas = [ev for ev in out if getattr(ev, "type", None) == EventType.STATE_DELTA]
    assert deltas, "expected at least one STATE_DELTA event"
    paths = {op["path"] for op in deltas[-1].delta}
    assert paths == {"/activity", "/stats"}
    last_activity = next(op["value"] for op in deltas[-1].delta if op["path"] == "/activity")
    assert last_activity[0]["title"] == "math_expert"


@pytest.mark.asyncio
async def test_no_event_emitted_after_run_finished():
    """AG-UI rejects any event after RUN_FINISHED; the final rail delta must precede it."""
    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import project_stream

    events = [
        {"type": "RUN_STARTED", "_t_ms": 0},
        {
            "type": "TOOL_CALL_START",
            "tool_call_id": "t1",
            "tool_call_name": "task",
            "parent_message_id": "lc_run--MAIN",
            "_t_ms": 10,
        },
        {"type": "TOOL_CALL_END", "tool_call_id": "t1", "_t_ms": 20},
        {"type": "RUN_FINISHED", "_t_ms": 30},
    ]

    out = [ev async for ev in project_stream(_aiter(events), mcp_servers=set())]

    types = [ev.get("type") if isinstance(ev, dict) else getattr(ev, "type", None) for ev in out]
    finished_idx = next(
        i for i, ev in enumerate(out) if isinstance(ev, dict) and ev.get("type") == "RUN_FINISHED"
    )
    assert finished_idx == len(out) - 1, (
        f"RUN_FINISHED must be the last event; got trailing {types[finished_idx + 1 :]}"
    )


def test_rail_agent_is_langgraph_agui_subclass():
    pytest.importorskip("copilotkit")
    from copilotkit import LangGraphAGUIAgent

    from autobots_devtools_shared_lib.dynagent.ui.rail_stream import RailAGUIAgent

    assert issubclass(RailAGUIAgent, LangGraphAGUIAgent)
