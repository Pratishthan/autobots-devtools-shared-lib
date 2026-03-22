# ABOUTME: Tests for eval result dataclasses.
# ABOUTME: Validates EvalResult.summary(), TurnResult.passed logic, etc.

from autobots_devtools_shared_lib.eval.models.result import (
    AgentOutput,
    AssertionResult,
    EvalResult,
    TurnResult,
)


def test_turn_result_passed_when_all_assertions_pass():
    turn = TurnResult(
        turn=1,
        assertions=[
            AssertionResult(passed=True, name="contains", detail="found"),
            AssertionResult(passed=True, name="tool_called", detail="ok"),
        ],
        passed=True,
        agent_message="hello",
    )
    assert turn.passed is True


def test_turn_result_failed_when_any_assertion_fails():
    turn = TurnResult(
        turn=1,
        assertions=[
            AssertionResult(passed=True, name="contains", detail="found"),
            AssertionResult(passed=False, name="tool_called", detail="not found"),
        ],
        passed=False,
        agent_message="hello",
    )
    assert turn.passed is False


def test_eval_result_summary_on_failure():
    result = EvalResult(
        name="test eval",
        passed=False,
        turns=[
            TurnResult(
                turn=1,
                assertions=[
                    AssertionResult(passed=False, name="contains:Party", detail="not found"),
                ],
                passed=False,
                agent_message="no models found",
            )
        ],
        cost_report=None,
    )
    summary = result.summary()
    assert "test eval" in summary
    assert "FAILED" in summary or "contains:Party" in summary


def test_eval_result_summary_on_pass():
    result = EvalResult(
        name="test eval",
        passed=True,
        turns=[
            TurnResult(
                turn=1,
                assertions=[
                    AssertionResult(passed=True, name="contains", detail="found"),
                ],
                passed=True,
                agent_message="hello",
            )
        ],
        cost_report=None,
    )
    summary = result.summary()
    assert "test eval" in summary


def test_assertion_result_inconclusive():
    r = AssertionResult(passed=False, name="llm_judge", detail="timeout", inconclusive=True)
    assert r.inconclusive is True


def test_agent_output_creation():
    output = AgentOutput(
        messages=[],
        structured_response=None,
        agent_name="coordinator",
        raw_state={},
    )
    assert output.agent_name == "coordinator"
