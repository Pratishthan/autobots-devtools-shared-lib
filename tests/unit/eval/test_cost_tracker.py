# ABOUTME: Tests for cost tracker baseline load/save and comparison functions.
# ABOUTME: Validates threshold-based warning detection and file I/O.
import json

import pytest

from autobots_devtools_shared_lib.eval.core.cost_tracker import (
    compare_with_baseline,
    load_baseline,
    save_baseline,
)
from autobots_devtools_shared_lib.eval.models.result import EvalCostSnapshot


@pytest.fixture()
def snapshot() -> EvalCostSnapshot:
    return EvalCostSnapshot(
        eval_name="test eval",
        agent="model-list-extractor",
        total_input_tokens=3200,
        total_output_tokens=600,
        total_cost_usd=0.008,
        total_latency_ms=4100,
        llm_calls=2,
        per_tool_tokens={"set_context_tool": 50, "mer_read_file_tool": 1900},
        timestamp="2026-03-26T10:00:00Z",
    )


class TestLoadBaseline:
    def test_loads_valid_file(self, tmp_path, snapshot):
        baseline_path = tmp_path / "cost_baseline.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "eval_name": "test eval",
                    "agent": "model-list-extractor",
                    "total_input_tokens": 3000,
                    "total_output_tokens": 500,
                    "total_cost_usd": 0.007,
                    "total_latency_ms": 3800,
                    "llm_calls": 2,
                    "per_tool_tokens": {},
                }
            )
        )
        result = load_baseline(str(baseline_path))
        assert result is not None
        assert result["total_input_tokens"] == 3000

    def test_returns_none_for_missing_file(self):
        result = load_baseline("/nonexistent/path.json")
        assert result is None


class TestSaveBaseline:
    def test_saves_snapshot(self, tmp_path, snapshot):
        path = tmp_path / "cost_baseline.json"
        save_baseline(snapshot, str(path))
        data = json.loads(path.read_text())
        assert data["total_input_tokens"] == 3200
        assert data["agent"] == "model-list-extractor"

    def test_creates_parent_dirs(self, tmp_path, snapshot):
        path = tmp_path / "nested" / "dir" / "baseline.json"
        save_baseline(snapshot, str(path))
        assert path.exists()


class TestCompareWithBaseline:
    def test_all_ok(self, snapshot):
        baseline = {
            "total_input_tokens": 3100,
            "total_output_tokens": 590,
            "total_cost_usd": 0.0078,
            "total_latency_ms": 4000,
            "llm_calls": 2,
        }
        thresholds = {"input_tokens": 20, "cost_usd": 25, "latency_ms": 30}
        deltas = compare_with_baseline(snapshot, baseline, thresholds)
        assert all(d.status == "ok" for d in deltas)

    def test_warning_on_threshold_breach(self, snapshot):
        baseline = {
            "total_input_tokens": 2000,  # actual is 3200 = +60%
            "total_output_tokens": 600,
            "total_cost_usd": 0.008,
            "total_latency_ms": 4100,
            "llm_calls": 2,
        }
        thresholds = {"input_tokens": 20}
        deltas = compare_with_baseline(snapshot, baseline, thresholds)
        token_delta = next(d for d in deltas if d.metric == "input_tokens")
        assert token_delta.status == "warning"
        assert token_delta.delta_pct > 50

    def test_decrease_is_always_ok(self, snapshot):
        baseline = {
            "total_input_tokens": 5000,  # actual is 3200 = -36%
            "total_output_tokens": 600,
            "total_cost_usd": 0.008,
            "total_latency_ms": 4100,
            "llm_calls": 2,
        }
        thresholds = {"input_tokens": 20}
        deltas = compare_with_baseline(snapshot, baseline, thresholds)
        token_delta = next(d for d in deltas if d.metric == "input_tokens")
        assert token_delta.status == "ok"

    def test_empty_thresholds_all_ok(self, snapshot):
        baseline = {
            "total_input_tokens": 100,
            "total_output_tokens": 100,
            "total_cost_usd": 0.001,
            "total_latency_ms": 100,
            "llm_calls": 1,
        }
        deltas = compare_with_baseline(snapshot, baseline, {})
        assert all(d.status == "ok" for d in deltas)
