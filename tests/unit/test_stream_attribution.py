# ABOUTME: Unit tests for StreamAttribution against the frozen 286-event spike stream.
# ABOUTME: Pins main-agent identification, per-subagent ownership, and nested-tool ownership.

import json
from pathlib import Path

import pytest

from autobots_devtools_shared_lib.dynagent.ui.stream_attribution import StreamAttribution

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
