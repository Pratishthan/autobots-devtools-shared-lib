# ABOUTME: Unit tests for the make_dynagent_eval factory function.
# ABOUTME: Verifies workspace staging, runner dispatch, and teardown behavior.

from __future__ import annotations

from unittest.mock import patch

from autobots_devtools_shared_lib.eval.models.eval_case import (
    Assertion,
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
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.run_linear_eval")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.setup_workspace")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.teardown_workspace")
    def test_calls_runner(self, mock_teardown, mock_setup, mock_run):
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

    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.run_linear_eval")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.setup_workspace")
    @patch("autobots_devtools_shared_lib.eval.pytest_plugin.fixtures.teardown_workspace")
    def test_calls_workspace_setup(self, mock_teardown, mock_setup, mock_run):
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
        mock_setup.assert_called_once()
        mock_teardown.assert_called_once()
