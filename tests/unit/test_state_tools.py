# ABOUTME: Unit tests for dynagent state management tools.
# ABOUTME: Covers command helpers, workspace file ops, and handoff validation.

from langgraph.types import Command

import dynagent.tools.state_tools as state_tools
from dynagent.tools.state_tools import (
    _do_read_file,
    _do_write_file,
    _validate_handoff,
    error_cmd,
    transition_cmd,
)

# --- Command helpers ---


def test_error_cmd_returns_command():
    result = error_cmd("Something went wrong", "tool-call-1")
    assert isinstance(result, Command)


def test_error_cmd_message_content():
    result = error_cmd("bad input", "tc-42")
    assert result.update is not None
    messages = result.update["messages"]
    assert len(messages) == 1
    assert messages[0].content == "bad input"
    assert messages[0].tool_call_id == "tc-42"


def test_error_cmd_does_not_set_agent_name():
    result = error_cmd("nope", "tc-1")
    assert result.update is not None
    assert "agent_name" not in result.update


def test_transition_cmd_returns_command():
    result = transition_cmd("moving on", "tc-2", "preface_agent")
    assert isinstance(result, Command)


def test_transition_cmd_sets_agent_name():
    result = transition_cmd("go", "tc-3", "features_agent")
    assert result.update is not None
    assert result.update["agent_name"] == "features_agent"


def test_transition_cmd_message_content():
    result = transition_cmd("hi", "tc-4", "coordinator")
    assert result.update is not None
    messages = result.update["messages"]
    assert len(messages) == 1
    assert messages[0].content == "hi"
    assert messages[0].tool_call_id == "tc-4"


def test_transition_cmd_passes_extra_updates():
    result = transition_cmd("x", "tc-5", "coordinator", foo="bar")
    assert result.update is not None
    assert result.update["foo"] == "bar"


# --- Workspace file ops ---


def test_write_file_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(state_tools, "WORKSPACE_BASE", tmp_path)
    result = _do_write_file("sess-1", "notes.md", "hello world")
    assert "Successfully wrote" in result
    assert (tmp_path / "sess-1" / "notes.md").read_text() == "hello world"


def test_write_file_creates_nested_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(state_tools, "WORKSPACE_BASE", tmp_path)
    _do_write_file("deep-session", "file.txt", "content")
    assert (tmp_path / "deep-session" / "file.txt").exists()


def test_write_file_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(state_tools, "WORKSPACE_BASE", tmp_path)
    _do_write_file("s", "f.txt", "first")
    _do_write_file("s", "f.txt", "second")
    assert (tmp_path / "s" / "f.txt").read_text() == "second"


def test_read_file_reads_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(state_tools, "WORKSPACE_BASE", tmp_path)
    (tmp_path / "sess-2").mkdir()
    (tmp_path / "sess-2" / "data.txt").write_text("payload")
    result = _do_read_file("sess-2", "data.txt")
    assert result == "payload"


def test_read_file_returns_error_for_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(state_tools, "WORKSPACE_BASE", tmp_path)
    result = _do_read_file("sess-x", "nope.txt")
    assert "Error" in result


def test_write_then_read_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(state_tools, "WORKSPACE_BASE", tmp_path)
    _do_write_file("rt", "loop.md", "roundtrip data")
    assert _do_read_file("rt", "loop.md") == "roundtrip data"


# --- Handoff validation ---


def test_validate_handoff_accepts_coordinator():
    assert _validate_handoff("coordinator") is None


def test_validate_handoff_accepts_all_section_agents():
    for agent in (
        "preface_agent",
        "getting_started_agent",
        "features_agent",
        "entity_agent",
    ):
        assert _validate_handoff(agent) is None, f"Should accept {agent}"


def test_validate_handoff_rejects_unknown():
    result = _validate_handoff("nonexistent_agent")
    assert result is not None
    assert "Invalid agent" in result
    assert "nonexistent_agent" in result


def test_validate_handoff_rejects_bro_tool_names():
    """BRO tool names are not valid agent targets."""
    result = _validate_handoff("update_section")
    assert result is not None
    assert "Invalid agent" in result
