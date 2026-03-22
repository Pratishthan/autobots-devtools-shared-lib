# ABOUTME: Tests for deterministic assertion functions.
# ABOUTME: Tests contains, regex, exact_match, schema_match, and tool_called assertions.

from langchain_core.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.eval.assertions.deterministic import (
    contains,
    exact_match,
    regex,
    schema_match,
    tool_called,
)
from autobots_devtools_shared_lib.eval.models.result import AgentOutput


def _make_output(content: str, tool_calls: list | None = None) -> AgentOutput:
    """Helper to build AgentOutput with a simple AI message."""
    ai_msg = AIMessage(content=content)
    if tool_calls:
        ai_msg.tool_calls = tool_calls
    return AgentOutput(
        messages=[HumanMessage(content="test"), ai_msg],
        structured_response=None,
        agent_name="test",
        raw_state={},
    )


def test_contains_passes():
    output = _make_output("Hello world, Party is here")
    result = contains(output, "Party")
    assert result.passed is True


def test_contains_fails():
    output = _make_output("Hello world")
    result = contains(output, "Party")
    assert result.passed is False


def test_contains_case_insensitive():
    output = _make_output("Hello Party")
    result = contains(output, "party")
    assert result.passed is True


def test_regex_passes():
    output = _make_output("Found 3 models: Party, Address, Contact")
    result = regex(output, r"\d+ models")
    assert result.passed is True


def test_regex_fails():
    output = _make_output("No models found")
    result = regex(output, r"\d+ models")
    assert result.passed is False


def test_exact_match_passes():
    output = _make_output("hello")
    result = exact_match(output, "hello")
    assert result.passed is True


def test_exact_match_fails():
    output = _make_output("hello world")
    result = exact_match(output, "hello")
    assert result.passed is False


def test_schema_match_passes(tmp_path):
    schema_file = tmp_path / "test_schema.json"
    schema_file.write_text('{"type": "object", "required": ["models"]}')
    output = _make_output('{"models": ["Party"]}')
    result = schema_match(output, str(schema_file))
    assert result.passed is True


def test_schema_match_fails(tmp_path):
    schema_file = tmp_path / "test_schema.json"
    schema_file.write_text('{"type": "object", "required": ["models"]}')
    output = _make_output('{"items": ["Party"]}')
    result = schema_match(output, str(schema_file))
    assert result.passed is False


def test_tool_called_passes():
    output = _make_output(
        "done",
        tool_calls=[{"name": "mer_read_file_tool", "args": {}, "id": "1"}],
    )
    result = tool_called(output, "mer_read_file_tool")
    assert result.passed is True


def test_tool_called_fails():
    output = _make_output("done", tool_calls=[])
    result = tool_called(output, "mer_read_file_tool")
    assert result.passed is False
