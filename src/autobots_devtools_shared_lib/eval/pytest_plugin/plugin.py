# ABOUTME: Pytest plugin for the dynagent eval framework.
# ABOUTME: Registers CLI options, markers, and session-level cost report generation.

from __future__ import annotations

import pytest

from autobots_devtools_shared_lib.eval.pytest_plugin.fixtures import make_dynagent_eval
from autobots_devtools_shared_lib.eval.pytest_plugin.reporting import (
    format_cost_summary,
    write_cost_report,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register eval-specific CLI options."""
    group = parser.getgroup("dynagent-eval", "Dynagent eval framework options")
    group.addoption(
        "--eval-dir",
        default="evals",
        help="Root directory for eval YAML files (default: evals)",
    )
    group.addoption(
        "--eval-tags",
        default=None,
        help="Only run evals matching these tags (comma-separated)",
    )
    group.addoption(
        "--eval-cost-report",
        default=None,
        help="Path to write cost report JSON",
    )
    group.addoption(
        "--eval-cost-deep",
        action="store_true",
        default=False,
        help="Enable Level 2 utilization analysis (requires extra LLM calls)",
    )
    group.addoption(
        "--eval-no-langfuse-score",
        action="store_true",
        default=False,
        help="Skip posting scores to Langfuse",
    )
    group.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden output files with current agent responses",
    )
    group.addoption(
        "--update-baseline",
        action="store_true",
        default=False,
        help="Save current cost snapshots as new baselines",
    )


@pytest.fixture
def dynagent_eval(request: pytest.FixtureRequest):
    """Fixture that provides a callable to run eval cases."""
    config = request.config
    return make_dynagent_eval(
        update_golden=config.getoption("--update-golden", default=False),
        update_baseline=config.getoption("--update-baseline", default=False),
        no_langfuse_score=config.getoption("--eval-no-langfuse-score", default=False),
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register eval markers."""
    config.addinivalue_line("markers", "eval: marks a test as a dynagent eval")
    config.addinivalue_line("markers", "eval_linear: marks a linear mode eval")
    config.addinivalue_line("markers", "eval_goal: marks a goal-based eval")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001
    """Write cost report at end of test session."""
    eval_results = getattr(session.config, "_eval_cost_reports", None)
    if not eval_results:
        return

    report_path = session.config.getoption("--eval-cost-report", default=None)
    if report_path:
        write_cost_report(eval_results, report_path)

    # Print terminal summary
    summary = format_cost_summary(eval_results)
    if summary:
        print(summary)  # noqa: T201,RUF100
