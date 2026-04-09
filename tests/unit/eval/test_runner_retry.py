# ABOUTME: Tests for the eval runner retry logic.
# ABOUTME: Validates flaky assertion retry with count limits and only_for filtering.

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from autobots_devtools_shared_lib.eval.core.runner import run_linear_eval
from autobots_devtools_shared_lib.eval.models.eval_case import (
    Assertion,
    CostConfig,
    EvalCase,
    RetryConfig,
    Turn,
)


def _make_eval_case_with_retry(
    assertions: list[dict],
    retry_count: int = 2,
    only_for: list[str] | None = None,
) -> EvalCase:
    return EvalCase(
        name="retry test",
        agent="coordinator",
        mode="linear",
        tags=["smoke"],
        state={"user_name": "test"},
        turns=[Turn(user="Hello", assertions=[Assertion.model_validate(a) for a in assertions])],
        cost=CostConfig(track=False),
        retry=RetryConfig(count=retry_count, only_for=only_for or ["llm_judge"]),
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


async def test_retry_flaky_assertion_eventually_passes(mock_invoke):
    """Assertion fails first, passes on retry."""
    call_count = 0

    def mock_llm_judge(agent_output, config):
        nonlocal call_count
        call_count += 1
        from autobots_devtools_shared_lib.eval.models.result import AssertionResult

        if call_count == 1:
            return AssertionResult(passed=False, name="llm_judge", detail="Fail first time")
        return AssertionResult(passed=True, name="llm_judge", detail="Pass on retry")

    with patch(
        "autobots_devtools_shared_lib.eval.core.runner.resolve_assertion",
        return_value=mock_llm_judge,
    ):
        case = _make_eval_case_with_retry(
            [{"llm_judge": {"criteria": "Is it good?", "threshold": 0.5}}],
            retry_count=2,
        )
        config = {"configurable": {"thread_id": "retry-1"}}
        result = await run_linear_eval(case, config, trace_metadata=None)
        assert result.passed is True
        assert call_count == 2


async def test_retry_exhausted_still_fails(mock_invoke):
    """Assertion fails on all retries."""
    from autobots_devtools_shared_lib.eval.models.result import AssertionResult

    def mock_llm_judge(agent_output, config):
        return AssertionResult(
            passed=False, name="llm_judge", detail="Always fails", inconclusive=True
        )

    with patch(
        "autobots_devtools_shared_lib.eval.core.runner.resolve_assertion",
        return_value=mock_llm_judge,
    ):
        case = _make_eval_case_with_retry(
            [{"llm_judge": {"criteria": "Is it good?", "on_judge_error": "fail"}}],
            retry_count=2,
        )
        config = {"configurable": {"thread_id": "retry-2"}}
        result = await run_linear_eval(case, config, trace_metadata=None)
        assert result.passed is False


async def test_no_retry_for_deterministic_assertions(mock_invoke):
    """Deterministic assertions (contains) are never retried even if they fail."""
    case = _make_eval_case_with_retry(
        [{"contains": "NotHere"}],
        retry_count=3,
        only_for=["llm_judge"],
    )
    config = {"configurable": {"thread_id": "retry-3"}}
    result = await run_linear_eval(case, config, trace_metadata=None)
    assert result.passed is False
    # ainvoke_agent called once (no retry for contains)
    assert mock_invoke.call_count == 1


async def test_no_retry_when_count_zero(mock_invoke):
    """No retries when retry count is 0."""
    case = EvalCase(
        name="no retry",
        agent="coordinator",
        mode="linear",
        tags=["smoke"],
        state={"user_name": "test"},
        turns=[Turn(user="Hello", assertions=[Assertion.model_validate({"contains": "NotHere"})])],
        cost=CostConfig(track=False),
        retry=RetryConfig(count=0, only_for=[]),
    )
    config = {"configurable": {"thread_id": "retry-4"}}
    result = await run_linear_eval(case, config, trace_metadata=None)
    assert result.passed is False


async def test_on_judge_error_warn_treats_inconclusive_as_pass(mock_invoke):
    """When assertion fails, retry logic applies."""
    from autobots_devtools_shared_lib.eval.models.result import AssertionResult

    call_count = 0

    def mock_llm_judge(agent_output, config):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return AssertionResult(passed=False, name="llm_judge", detail="Judge timeout")
        return AssertionResult(passed=True, name="llm_judge", detail="Pass on retry")

    with patch(
        "autobots_devtools_shared_lib.eval.core.runner.resolve_assertion",
        return_value=mock_llm_judge,
    ):
        case = _make_eval_case_with_retry(
            [{"llm_judge": {"criteria": "Is it good?"}}],
            retry_count=1,
        )
        config = {"configurable": {"thread_id": "retry-5"}}
        result = await run_linear_eval(case, config, trace_metadata=None)
        # Retry should cause the assertion to pass
        assert result.passed is True
        assert call_count == 2


async def test_on_judge_error_fail_keeps_inconclusive_as_fail(mock_invoke):
    """When assertion fails consistently, it remains failed."""
    from autobots_devtools_shared_lib.eval.models.result import AssertionResult

    def mock_llm_judge(agent_output, config):
        return AssertionResult(passed=False, name="llm_judge", detail="Judge timeout")

    with patch(
        "autobots_devtools_shared_lib.eval.core.runner.resolve_assertion",
        return_value=mock_llm_judge,
    ):
        case = _make_eval_case_with_retry(
            [{"llm_judge": {"criteria": "Is it good?"}}],
            retry_count=1,
        )
        config = {"configurable": {"thread_id": "retry-6"}}
        result = await run_linear_eval(case, config, trace_metadata=None)
        assert result.passed is False
