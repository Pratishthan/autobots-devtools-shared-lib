# ABOUTME: Unit tests for StreamAttribution against the frozen 286-event spike stream.
# ABOUTME: Pins main-agent identification, per-subagent ownership, and nested-tool ownership.

import json
from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.ui.stream_attribution import (
    DispatchInfo,
    StreamAttribution,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "agui_stream.jsonl"


def _load_raw_events() -> list[dict]:
    """Unwrap the AG-UI RAW envelopes into raw astream_events dicts."""
    lines = [json.loads(line) for line in _FIXTURE.read_text().splitlines() if line.strip()]
    return [line["event"] for line in lines if line.get("type") == "RAW" and line.get("event")]


def _tool_start(events: list[dict], tool_name: str) -> dict:
    for e in events:
        if e.get("event") == "on_tool_start" and e.get("name") == tool_name:
            return e
    raise AssertionError(f"no on_tool_start for {tool_name!r} in fixture")


@pytest.fixture
def observed() -> StreamAttribution:
    attr = StreamAttribution()
    for event in _load_raw_events():
        attr.observe(event)
    return attr


def test_main_agent_is_first_chat_model_agent(observed):
    assert observed.main_agent == "assistant"


def test_main_agent_tool_is_main(observed):
    event = _tool_start(_load_raw_events(), "spike_tools__get_secret_number")
    assert observed.owner(event) == "assistant"
    assert observed.is_main(observed.owner(event)) is True


def test_nested_subagent_tool_self_attributes(observed):
    event = _tool_start(_load_raw_events(), "spike_tools__get_weather")
    assert observed.owner(event) == "weather_expert"
    assert observed.is_main(observed.owner(event)) is False


def test_task_dispatch_is_detected(observed):
    task_event = _tool_start(_load_raw_events(), "task")
    weather_event = _tool_start(_load_raw_events(), "spike_tools__get_weather")
    assert StreamAttribution.is_task_dispatch(task_event) is True
    assert StreamAttribution.is_task_dispatch(weather_event) is False


def test_is_main_fail_open_when_agent_none():
    attr = StreamAttribution()  # nothing observed; main_agent is None
    assert attr.main_agent is None
    assert attr.is_main(None) is True


def test_owner_falls_back_to_run_agent_map_when_metadata_absent():
    attr = StreamAttribution()
    attr.observe(
        {"event": "on_chat_model_start", "run_id": "r1", "metadata": {"lc_agent_name": "assistant"}}
    )
    # A later event for the same run_id whose metadata momentarily lacks the agent name.
    stripped = {"event": "on_chat_model_stream", "run_id": "r1", "metadata": {}}
    assert attr.owner(stripped) == "assistant"


def test_main_only_stream_treats_every_agent_as_main():
    attr = StreamAttribution()
    for run in ("r1", "r2"):
        attr.observe(
            {"event": "on_chat_model_stream", "run_id": run, "metadata": {"lc_agent_name": "solo"}}
        )
    assert attr.main_agent == "solo"
    assert attr.is_main("solo") is True


def test_two_concurrent_subagents_have_distinct_owners():
    attr = StreamAttribution()
    attr.observe(
        {"event": "on_chat_model_start", "run_id": "m", "metadata": {"lc_agent_name": "assistant"}}
    )
    weather = {
        "event": "on_chat_model_stream",
        "run_id": "w",
        "metadata": {"lc_agent_name": "weather_expert"},
    }
    math = {
        "event": "on_chat_model_stream",
        "run_id": "n",
        "metadata": {"lc_agent_name": "math_expert"},
    }
    attr.observe(weather)
    attr.observe(math)
    assert attr.owner(weather) == "weather_expert"
    assert attr.owner(math) == "math_expert"
    assert attr.is_main("weather_expert") is False
    assert attr.is_main("math_expert") is False


def _chat_stream(agent, run_id, parent_ids):
    return {
        "event": "on_chat_model_stream",
        "run_id": run_id,
        "parent_ids": parent_ids,
        "metadata": {"lc_agent_name": agent},
    }


def test_task_dispatch_is_recorded_with_type_and_description(observed):
    # The frozen fixture dispatches math_expert and weather_expert.
    types = {d.subagent_type for d in observed.dispatches.values()}
    assert types == {"math_expert", "weather_expert"}
    descriptions = [d.description for d in observed.dispatches.values()]
    assert any(desc and "17 times 3" in desc for desc in descriptions)


def test_dispatch_of_maps_subagent_event_to_its_task_run_id(observed):
    # Two dispatches share a UUIDv7 time-prefix; attribution must use full ids.
    by_type = {d.subagent_type: rid for rid, d in observed.dispatches.items()}
    math_run_id = by_type["math_expert"]
    weather_run_id = by_type["weather_expert"]
    assert math_run_id != weather_run_id
    assert math_run_id[:13] == weather_run_id[:13]  # prefix collision is real

    ev_math = _chat_stream("math_expert", "model-a", parent_ids=["root", math_run_id])
    ev_weather = _chat_stream("weather_expert", "model-b", parent_ids=["root", weather_run_id])
    assert observed.dispatch_of(ev_math) == math_run_id
    assert observed.dispatch_of(ev_weather) == weather_run_id


def test_dispatch_of_returns_none_without_task_ancestor(observed):
    ev = _chat_stream("assistant", "m", parent_ids=[])
    assert observed.dispatch_of(ev) is None


def test_dispatch_of_returns_nearest_ancestor():
    attr = StreamAttribution()
    outer = _tool_start_task("outer", "outer_agent", "outer task")
    inner = _tool_start_task("inner", "inner_agent", "inner task")
    attr.observe(outer)
    attr.observe(inner)
    # parent_ids ordered root->parent: outer is shallower, inner is deeper.
    ev = {
        "event": "on_chat_model_stream",
        "run_id": "deep-model",
        "parent_ids": ["root", "outer", "mid", "inner"],
        "metadata": {"lc_agent_name": "inner_agent"},
    }
    assert attr.dispatch_of(ev) == "inner"


def test_dispatch_label_combines_type_and_trimmed_description():
    attr = StreamAttribution()
    attr.observe(_tool_start_task("r1", "general-purpose", "Research Rust pros and cons"))
    assert attr.dispatch_label("r1") == "general-purpose · Research Rust pros and cons"


def test_dispatch_label_trims_long_description_and_collapses_newlines():
    attr = StreamAttribution()
    long_desc = "First line about the task\nsecond line " + "x" * 100
    attr.observe(_tool_start_task("r1", "gp", long_desc))
    label = attr.dispatch_label("r1")
    assert "\n" not in label
    assert len(label) <= 80  # "gp · " + ~60 chars + ellipsis budget


def test_dispatch_label_falls_back_when_input_unparseable():
    attr = StreamAttribution()
    bad = {
        "event": "on_tool_start",
        "name": "task",
        "run_id": "r1",
        "data": {"input": "not-a-dict"},
    }
    attr.observe(bad)  # must not raise
    assert attr.dispatches["r1"] == DispatchInfo(None, None)
    assert attr.dispatch_label("r1") == "sub-agent"


def test_subagent_key_prefers_dispatch_then_falls_back_to_agent_name():
    attr = StreamAttribution()
    attr.observe(
        {"event": "on_chat_model_start", "run_id": "m", "metadata": {"lc_agent_name": "assistant"}}
    )
    attr.observe(_tool_start_task("disp1", "general-purpose", "Research Rust"))

    dispatch_event = _chat_stream("general-purpose", "model-x", parent_ids=["disp1"])
    assert attr.subagent_key(dispatch_event) == "disp1"

    legacy_event = _chat_stream("weather_expert", "model-y", parent_ids=[])
    assert attr.subagent_key(legacy_event) == "weather_expert"

    main_event = _chat_stream("assistant", "model-z", parent_ids=[])
    assert attr.subagent_key(main_event) is None


def test_step_label_uses_dispatch_label_for_known_dispatch_else_bare_key():
    attr = StreamAttribution()
    attr.observe(_tool_start_task("disp1", "general-purpose", "Research Rust"))
    assert attr.step_label("disp1") == "general-purpose · Research Rust"
    assert attr.step_label("weather_expert") == "weather_expert"


def _tool_start_task(run_id, subagent_type, description):
    return {
        "event": "on_tool_start",
        "name": "task",
        "run_id": run_id,
        "data": {"input": {"subagent_type": subagent_type, "description": description}},
    }
