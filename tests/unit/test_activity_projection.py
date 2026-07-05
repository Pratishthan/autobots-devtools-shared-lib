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
    assert titles[0].startswith("weather_expert · ")
    assert titles[1].startswith("math_expert · ")
    assert titles[2] == "get_secret_number"


def test_weather_subagent_item_folds_nested_mcp_call(projection):
    weather = projection["activity"][0]
    assert weather["dot"] == "var(--info)"
    assert weather["glow"] is False
    assert weather["title"].startswith("weather_expert · ")
    assert weather["mono"] == "MCP get_weather"
    assert weather["sub"] == "completed · 5837ms · 9220 tok"
    assert weather["isRunning"] is False


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


def _raw(event):
    return {"type": "RAW", "event": event}


def _agui_task_row(tcid, t_start, t_end):
    # AG-UI events that build one task rail row keyed by tcid.
    return [
        {
            "type": "TOOL_CALL_START",
            "tool_call_id": tcid,
            "tool_call_name": "task",
            "parent_message_id": "lc_run--COORD",
            "_t_ms": t_start,
        },
        {"type": "TOOL_CALL_END", "tool_call_id": tcid, "_t_ms": t_end},
    ]


def test_same_type_dispatches_get_distinct_labels_and_isolated_nested_tools():
    from autobots_devtools_shared_lib.dynagent.ui.activity_projection import ActivityProjection

    proj = ActivityProjection(mcp_servers={"spike_tools"})
    proj.observe({"type": "RUN_STARTED", "_t_ms": 0})

    # Coordinator model event first, so _first_agent (the main agent) is "assistant" and
    # subagent tools fold into their task rows instead of becoming top-level rows.
    proj.observe(
        _raw(
            {
                "event": "on_chat_model_stream",
                "run_id": "COORD",
                "parent_ids": [],
                "metadata": {"lc_agent_name": "assistant"},
            }
        )
    )

    # Two same-type dispatches (RAW on_tool_start registers them in StreamAttribution).
    proj.observe(
        _raw(
            {
                "event": "on_tool_start",
                "name": "task",
                "run_id": "disp-A",
                "data": {
                    "input": {"subagent_type": "general-purpose", "description": "Research Rust"}
                },
            }
        )
    )
    proj.observe(
        _raw(
            {
                "event": "on_tool_start",
                "name": "task",
                "run_id": "disp-B",
                "data": {
                    "input": {"subagent_type": "general-purpose", "description": "Research Kotlin"}
                },
            }
        )
    )
    # Each subagent's model-run points at its dispatch via parent_ids.
    proj.observe(
        _raw(
            {
                "event": "on_chat_model_stream",
                "run_id": "model-A",
                "parent_ids": ["disp-A"],
                "metadata": {"lc_agent_name": "general-purpose"},
            }
        )
    )
    proj.observe(
        _raw(
            {
                "event": "on_chat_model_stream",
                "run_id": "model-B",
                "parent_ids": ["disp-B"],
                "metadata": {"lc_agent_name": "general-purpose"},
            }
        )
    )
    # toolu -> dispatch bridge, from RAW on_tool_end(task) output ToolMessage.tool_call_id.
    proj.observe(
        _raw(
            {
                "event": "on_tool_end",
                "name": "task",
                "run_id": "disp-A",
                "data": {"output": {"tool_call_id": "toolu-A"}},
            }
        )
    )
    proj.observe(
        _raw(
            {
                "event": "on_tool_end",
                "name": "task",
                "run_id": "disp-B",
                "data": {"output": {"tool_call_id": "toolu-B"}},
            }
        )
    )

    # AG-UI task rows (keyed by toolu) + one nested MCP tool per dispatch.
    for ev in _agui_task_row("toolu-A", 10, 40):
        proj.observe(ev)
    for ev in _agui_task_row("toolu-B", 11, 41):
        proj.observe(ev)
    # Nested tool under dispatch A's model-run.
    proj.observe(
        {
            "type": "TOOL_CALL_START",
            "tool_call_id": "nested-A",
            "tool_call_name": "spike_tools__grep",
            "parent_message_id": "lc_run--model-A",
            "_t_ms": 20,
        }
    )
    proj.observe({"type": "TOOL_CALL_END", "tool_call_id": "nested-A", "_t_ms": 25})

    snap = proj.snapshot()
    rows = {r["title"]: r for r in snap["activity"] if r["title"].startswith("general-purpose")}
    assert set(rows) == {
        "general-purpose · Research Rust",
        "general-purpose · Research Kotlin",
    }
    # Nested grep folds only into dispatch A; dispatch B has no nested tool.
    assert rows["general-purpose · Research Rust"]["mono"] == "MCP grep"
    assert rows["general-purpose · Research Kotlin"]["mono"] == ""


@pytest.mark.parametrize("bad_data", [None, [], ["not", "a", "dict"]])
def test_on_tool_end_task_with_non_dict_data_does_not_raise(bad_data):
    from autobots_devtools_shared_lib.dynagent.ui.activity_projection import ActivityProjection

    proj = ActivityProjection(mcp_servers=set())
    # Fail-safe: a RAW on_tool_end(task) whose `data` is None / a list must not crash.
    proj.observe(
        _raw(
            {
                "event": "on_tool_end",
                "name": "task",
                "run_id": "disp-A",
                "data": bad_data,
            }
        )
    )
    # No toolu -> dispatch mapping was recorded, so the AG-UI task row falls back to
    # its parsed subagent_type (here absent) -> "sub-agent".
    proj.observe(
        {
            "type": "TOOL_CALL_START",
            "tool_call_id": "toolu-A",
            "tool_call_name": "task",
            "parent_message_id": "lc_run--COORD",
            "_t_ms": 10,
        }
    )
    proj.observe({"type": "TOOL_CALL_END", "tool_call_id": "toolu-A", "_t_ms": 20})

    row = proj.snapshot()["activity"][0]
    assert row["title"] == "sub-agent"
