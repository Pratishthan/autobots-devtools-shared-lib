# ABOUTME: Tests for LLM-as-judge assertion functions.
# ABOUTME: Uses mocked OpenEvals evaluator to verify scoring logic and error handling.

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.eval.assertions.llm_judge import llm_judge, trajectory_quality
from autobots_devtools_shared_lib.eval.models.result import AgentOutput


def _make_output(content: str) -> AgentOutput:
    """Helper to build AgentOutput with a simple AI message."""
    return AgentOutput(
        messages=[HumanMessage(content="test"), AIMessage(content=content)],
        structured_response=None,
        agent_name="test",
        raw_state={},
    )


def test_llm_judge_passes_above_threshold():
    mock_evaluator = MagicMock(return_value={"score": 0.9, "reasoning": "Good response"})
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Here are the models: Party, Address, Contact")
        result = llm_judge(output, {"criteria": "Lists domain models", "threshold": 0.8})
        assert result.passed is True
        assert "0.9" in result.detail


def test_llm_judge_fails_below_threshold():
    mock_evaluator = MagicMock(return_value={"score": 0.3, "reasoning": "Incomplete"})
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("I don't know")
        result = llm_judge(output, {"criteria": "Lists domain models", "threshold": 0.8})
        assert result.passed is False
        assert "0.3" in result.detail


def test_llm_judge_default_threshold():
    """Default threshold is 0.5."""
    mock_evaluator = MagicMock(return_value={"score": 0.6, "reasoning": "Decent"})
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Some response")
        result = llm_judge(output, {"criteria": "Is it helpful?"})
        assert result.passed is True


def test_llm_judge_error_returns_inconclusive():
    """When the judge LLM fails, return inconclusive result."""
    mock_evaluator = MagicMock(side_effect=RuntimeError("LLM timeout"))
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Some response")
        result = llm_judge(output, {"criteria": "Is it good?"})
        assert result.passed is False
        assert result.inconclusive is True
        assert "LLM timeout" in result.detail


def test_llm_judge_string_config():
    """Simple string config treated as criteria with default threshold."""
    mock_evaluator = MagicMock(return_value={"score": 0.8, "reasoning": "Good"})
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Response")
        result = llm_judge(output, "Is the response helpful?")
        assert result.passed is True


def test_trajectory_quality_passes():
    mock_evaluator = MagicMock(return_value={"score": 0.85, "reasoning": "Good tool usage"})
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Done")
        result = trajectory_quality(
            output, {"criteria": "Agent used tools efficiently", "threshold": 0.7}
        )
        assert result.passed is True


def test_trajectory_quality_fails():
    mock_evaluator = MagicMock(return_value={"score": 0.3, "reasoning": "Redundant tool calls"})
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Done")
        result = trajectory_quality(
            output, {"criteria": "Agent used tools efficiently", "threshold": 0.7}
        )
        assert result.passed is False


def test_trajectory_quality_error_returns_inconclusive():
    mock_evaluator = MagicMock(side_effect=RuntimeError("LLM error"))
    with patch(
        "autobots_devtools_shared_lib.eval.assertions.llm_judge.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        output = _make_output("Done")
        result = trajectory_quality(output, {"criteria": "Efficient"})
        assert result.passed is False
        assert result.inconclusive is True
