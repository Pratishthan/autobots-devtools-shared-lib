# ABOUTME: Unit tests for the make_dynagent_eval factory function.
# ABOUTME: Verifies workspace staging, runner dispatch, and teardown behavior.

from __future__ import annotations

from unittest.mock import patch

from autobots_devtools_shared_lib.eval.models.eval_case import (
    Assertion,
    CostConfig,
    EvalCase,
    Turn,
)
from autobots_devtools_shared_lib.eval.pytest_plugin.fixtures import make_dynagent_eval


def _make_eval_case(**overrides) -> EvalCase:
    defaults: dict = {
        "name": "test eval",
        "agent": "model-list-extractor",
        "mode": "linear",
        "tags": ["smoke"],
        "turns": [
            Turn(
                user="Extract models",
                assertions=[Assertion(name="contains", config="Party")],
            )
        ],
    }
    defaults.update(overrides)
    return EvalCase(**defaults)


class TestMakeDynagentEval:
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.post_scores")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.run_linear_eval")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.setup_workspace")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.teardown_workspace")
    def test_calls_runner(self, mock_teardown, mock_setup, mock_run, mock_post_scores):
        from autobots_devtools_shared_lib.eval.models.result import EvalResult

        mock_run.return_value = EvalResult(
            name="test", passed=True, turns=[], cost_snapshot=None, cost_deltas=None
        )

        eval_fn = make_dynagent_eval(
            update_golden=False,
            update_baseline=False,
            no_langfuse_score=False,
        )
        case = _make_eval_case()
        result = eval_fn(case)
        assert result.passed is True
        mock_run.assert_called_once()

    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.post_scores")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.run_linear_eval")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.setup_workspace")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.teardown_workspace")
    def test_calls_workspace_setup(self, mock_teardown, mock_setup, mock_run, mock_post_scores):
        from autobots_devtools_shared_lib.eval.models.result import EvalResult

        mock_run.return_value = EvalResult(
            name="test", passed=True, turns=[], cost_snapshot=None, cost_deltas=None
        )

        eval_fn = make_dynagent_eval(
            update_golden=False,
            update_baseline=False,
            no_langfuse_score=False,
        )
        case = _make_eval_case()
        eval_fn(case)
        mock_setup.assert_called_once_with(case.setup, mock_setup.call_args[0][1])
        mock_teardown.assert_called_once()

    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.post_scores")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.query_langfuse_cost")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.run_linear_eval")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.setup_workspace")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.teardown_workspace")
    def test_cost_tracking_sets_snapshot(
        self, mock_teardown, mock_setup, mock_run, mock_query_cost, mock_post_scores
    ):
        from autobots_devtools_shared_lib.eval.models.result import EvalCostSnapshot, EvalResult

        mock_run.return_value = EvalResult(
            name="test", passed=True, turns=[], cost_snapshot=None, cost_deltas=None
        )
        snapshot = EvalCostSnapshot(
            eval_name="test eval",
            agent="model-list-extractor",
            total_input_tokens=100,
            total_output_tokens=50,
            total_cost_usd=0.001,
            total_latency_ms=500,
            llm_calls=1,
            per_tool_tokens={},
            timestamp="2026-03-31T00:00:00",
        )
        mock_query_cost.return_value = snapshot

        eval_fn = make_dynagent_eval(
            update_golden=False,
            update_baseline=False,
            no_langfuse_score=True,
        )
        case = _make_eval_case(cost=CostConfig(track=True))
        result = eval_fn(case)

        mock_query_cost.assert_called_once()
        assert result.cost_snapshot is snapshot
