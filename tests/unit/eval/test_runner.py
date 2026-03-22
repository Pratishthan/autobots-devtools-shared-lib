# ABOUTME: Tests for the linear eval runner.
# ABOUTME: Uses mocked invoke_agent to verify turn execution and assertion flow.

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.eval.core.runner import run_linear_eval
from autobots_devtools_shared_lib.eval.models.eval_case import (
    Assertion,
    CostConfig,
    EvalCase,
    Turn,
)


def _make_eval_case(assertions: list[dict]) -> EvalCase:
    return EvalCase(
        name="test eval",
        agent="coordinator",
        mode="linear",
        tags=["smoke"],
        state={"user_name": "test"},
        turns=[Turn(user="Hello", assertions=[Assertion.model_validate(a) for a in assertions])],
        cost=CostConfig(track=False),
    )


@pytest.fixture
def mock_invoke():
    with patch(
        "autobots_devtools_shared_lib.eval.core.runner.ainvoke_agent",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there, Party is here"),
            ],
            "agent_name": "coordinator",
            "structured_response": None,
        }
        yield mock


async def test_linear_single_turn_passes(mock_invoke):
    case = _make_eval_case([{"contains": "Party"}])
    config = {"configurable": {"thread_id": "test-1"}}
    result = await run_linear_eval(case, config, trace_metadata=None)
    assert result.passed is True
    assert len(result.turns) == 1
    assert result.turns[0].passed is True


async def test_linear_single_turn_fails(mock_invoke):
    case = _make_eval_case([{"contains": "NotHere"}])
    config = {"configurable": {"thread_id": "test-2"}}
    result = await run_linear_eval(case, config, trace_metadata=None)
    assert result.passed is False
    assert result.turns[0].passed is False


async def test_linear_multiple_assertions(mock_invoke):
    case = _make_eval_case([{"contains": "Party"}, {"contains": "Hi"}])
    config = {"configurable": {"thread_id": "test-3"}}
    result = await run_linear_eval(case, config, trace_metadata=None)
    assert result.passed is True
    assert len(result.turns[0].assertions) == 2


async def test_linear_agent_error(mock_invoke):
    mock_invoke.side_effect = RuntimeError("LLM failed")
    case = _make_eval_case([{"contains": "anything"}])
    config = {"configurable": {"thread_id": "test-4"}}
    result = await run_linear_eval(case, config, trace_metadata=None)
    assert result.passed is False
    assert result.error is not None
    assert "LLM failed" in result.error
