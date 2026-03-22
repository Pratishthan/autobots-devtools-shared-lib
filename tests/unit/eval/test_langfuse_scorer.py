# ABOUTME: Tests for the Langfuse score posting module.
# ABOUTME: Validates scores are posted correctly and graceful degradation when unavailable.

from unittest.mock import MagicMock, patch

from autobots_devtools_shared_lib.eval.models.result import (
    AssertionResult,
    EvalResult,
    TurnResult,
)
from autobots_devtools_shared_lib.eval.scoring.langfuse_scorer import post_scores


def test_post_scores_skips_when_langfuse_unavailable():
    result = EvalResult(name="test", passed=True, turns=[], cost_report=None)
    with patch(
        "autobots_devtools_shared_lib.eval.scoring.langfuse_scorer.get_langfuse_client",
        return_value=None,
    ):
        # Should not raise
        post_scores("session-1", result)


def test_post_scores_calls_score():
    mock_client = MagicMock()
    mock_client.fetch_traces.return_value = MagicMock(data=[MagicMock(id="trace-abc")])
    result = EvalResult(
        name="test eval",
        passed=True,
        turns=[
            TurnResult(
                turn=1,
                assertions=[
                    AssertionResult(passed=True, name="contains:Party", detail="found"),
                ],
                passed=True,
                agent_message="hello",
            )
        ],
        cost_report=None,
    )
    with patch(
        "autobots_devtools_shared_lib.eval.scoring.langfuse_scorer.get_langfuse_client",
        return_value=mock_client,
    ):
        post_scores("session-1", result)
        assert mock_client.score.called
