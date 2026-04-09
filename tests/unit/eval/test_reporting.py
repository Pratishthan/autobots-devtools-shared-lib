# ABOUTME: Tests for eval cost reporting - terminal summary and JSON output.
# ABOUTME: Covers format_cost_summary and write_cost_report functions.
import json

from autobots_devtools_shared_lib.eval.models.result import (
    CostDelta,
    EvalCostSnapshot,
    EvalResult,
)
from autobots_devtools_shared_lib.eval.pytest_plugin.reporting import (
    format_cost_summary,
    write_cost_report,
)


class TestFormatCostSummary:
    def test_with_deltas(self):
        results = [
            EvalResult(
                name="Model list extraction",
                passed=True,
                turns=[],
                cost_snapshot=EvalCostSnapshot(
                    eval_name="Model list extraction",
                    agent="model-list-extractor",
                    total_input_tokens=3580,
                    total_output_tokens=610,
                    total_cost_usd=0.009,
                    total_latency_ms=3900,
                    llm_calls=2,
                    per_tool_tokens={},
                    timestamp="2026-03-26T10:00:00Z",
                ),
                cost_deltas=[
                    CostDelta(
                        metric="input_tokens",
                        baseline=3200,
                        actual=3580,
                        delta_pct=11.9,
                        status="ok",
                    ),
                    CostDelta(
                        metric="cost_usd",
                        baseline=0.008,
                        actual=0.009,
                        delta_pct=12.5,
                        status="warning",
                    ),
                ],
            )
        ]
        text = format_cost_summary(results)
        assert "model-list-extractor" in text
        assert "3580" in text
        assert "warning" in text.lower() or "⚠" in text

    def test_no_cost_data(self):
        results = [
            EvalResult(name="test", passed=True, turns=[], cost_snapshot=None, cost_deltas=None)
        ]
        text = format_cost_summary(results)
        assert "no cost data" in text.lower() or text.strip() == ""


class TestWriteCostReport:
    def test_writes_json(self, tmp_path):
        results = [
            EvalResult(
                name="test eval",
                passed=True,
                turns=[],
                cost_snapshot=EvalCostSnapshot(
                    eval_name="test eval",
                    agent="model-list-extractor",
                    total_input_tokens=3200,
                    total_output_tokens=600,
                    total_cost_usd=0.008,
                    total_latency_ms=4100,
                    llm_calls=2,
                    per_tool_tokens={"mer_read_file_tool": 1900},
                    timestamp="2026-03-26T10:00:00Z",
                ),
                cost_deltas=[
                    CostDelta(
                        metric="input_tokens",
                        baseline=3000,
                        actual=3200,
                        delta_pct=6.7,
                        status="ok",
                    ),
                ],
            )
        ]
        path = tmp_path / "report.json"
        write_cost_report(results, str(path))
        data = json.loads(path.read_text())
        assert len(data["evals"]) == 1
        assert data["evals"][0]["agent"] == "model-list-extractor"

    def test_creates_parent_dirs(self, tmp_path):
        results = [
            EvalResult(name="test", passed=True, turns=[], cost_snapshot=None, cost_deltas=None)
        ]
        path = tmp_path / "nested" / "dir" / "report.json"
        write_cost_report(results, str(path))
        assert path.exists()
