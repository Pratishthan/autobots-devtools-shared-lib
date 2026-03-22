# ABOUTME: Tests for cost report JSON writing and terminal summary.
# ABOUTME: Validates report format and file output.

import json

from autobots_devtools_shared_lib.eval.models.cost import (
    CostReport,
    TokenAttribution,
    TurnCost,
)
from autobots_devtools_shared_lib.eval.models.result import EvalResult
from autobots_devtools_shared_lib.eval.pytest_plugin.reporting import (
    format_terminal_summary,
    write_cost_report,
)


def _make_report() -> CostReport:
    return CostReport(
        eval_name="test eval",
        agent="coordinator",
        turns=[
            TurnCost(
                turn=1,
                model="gemini-2.0-flash",
                input_tokens=3200,
                output_tokens=600,
                cost_usd=0.035,
                latency_ms=1200,
                attribution=TokenAttribution(
                    system_prompt_tokens=800,
                    conversation_history_tokens=150,
                    tool_result_tokens=2100,
                    tools=[],
                    overhead_tokens=150,
                ),
            )
        ],
        total_input_tokens=3200,
        total_output_tokens=600,
        total_cost_usd=0.035,
        total_latency_ms=1200,
        llm_calls=1,
        lowest_utilization_tools=[],
        recommendations=[],
    )


def test_write_cost_report_creates_json(tmp_path):
    report_path = tmp_path / "report.json"
    results = [EvalResult(name="test", passed=True, turns=[], cost_report=_make_report())]
    write_cost_report(str(report_path), results)
    assert report_path.exists()
    data = json.loads(report_path.read_text())
    assert "summary" in data
    assert "evals" in data


def test_terminal_summary_format():
    results = [EvalResult(name="test", passed=True, turns=[], cost_report=_make_report())]
    summary = format_terminal_summary(results)
    assert "eval cost summary" in summary.lower() or "total" in summary.lower()
