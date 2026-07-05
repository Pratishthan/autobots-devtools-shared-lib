# ABOUTME: Fixture-driven unit tests for the AG-UI activity-rail projection.
# ABOUTME: Pins exact activity[]/stats{} derived from the frozen 286-event spike stream.

import json
from pathlib import Path

import pytest

_FIXTURE = Path(__file__).parent / "fixtures" / "agui_stream.jsonl"


def _load_events():
    return [json.loads(line) for line in _FIXTURE.read_text().splitlines() if line.strip()]


@pytest.fixture
def projection():
    from autobots_devtools_shared_lib.dynagent.ui.activity_projection import project_events

    return project_events(_load_events(), mcp_servers={"spike_tools"})


def test_stats_are_summed_across_all_agents(projection):
    assert projection["stats"] == {"tokens": 29385, "tools": 4, "latency": 9910}


def test_activity_has_three_items_in_start_order(projection):
    titles = [item["title"] for item in projection["activity"]]
    assert titles == ["weather_expert", "math_expert", "get_secret_number"]


def test_weather_subagent_item_folds_nested_mcp_call(projection):
    weather = projection["activity"][0]
    assert weather == {
        "dot": "var(--info)",
        "glow": False,
        "title": "weather_expert",
        "mono": "MCP get_weather",
        "sub": "completed · 5837ms · 9220 tok",
        "isRunning": False,
    }


def test_math_subagent_item_has_no_nested_call(projection):
    math = projection["activity"][1]
    assert math["dot"] == "var(--info)"
    assert math["mono"] == ""
    assert math["sub"] == "completed · 1967ms · 4361 tok"
    assert math["isRunning"] is False


def test_main_agent_mcp_tool_is_its_own_item(projection):
    secret = projection["activity"][2]
    assert secret == {
        "dot": "var(--accent)",
        "glow": False,
        "title": "get_secret_number",
        "mono": "MCP get_secret_number",
        "sub": "completed · 333ms",
        "isRunning": False,
    }


def test_running_item_before_result_glows():
    from autobots_devtools_shared_lib.dynagent.ui.activity_projection import ActivityProjection

    proj = ActivityProjection(mcp_servers={"spike_tools"})
    proj.observe({"type": "RUN_STARTED", "_t_ms": 0})
    proj.observe(
        {
            "type": "TOOL_CALL_START",
            "tool_call_id": "t1",
            "tool_call_name": "task",
            "parent_message_id": "lc_run--MAIN",
            "_t_ms": 10,
        }
    )
    for delta in ['{"subagent_type"', ': "math_expert"}']:
        proj.observe({"type": "TOOL_CALL_ARGS", "tool_call_id": "t1", "delta": delta})
    proj.observe({"type": "TOOL_CALL_END", "tool_call_id": "t1", "_t_ms": 20})

    item = proj.snapshot()["activity"][0]
    assert item["title"] == "math_expert"
    assert item["isRunning"] is True
    assert item["glow"] is True
    assert item["sub"] == "running"
