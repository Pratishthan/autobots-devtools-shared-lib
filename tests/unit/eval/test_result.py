from autobots_devtools_shared_lib.eval.models.result import (
    AssertionResult,
    CostDelta,
    EvalCostSnapshot,
    EvalResult,
    TurnResult,
)


class TestAssertionResult:
    def test_passed(self):
        r = AssertionResult(passed=True, name="contains:Party", detail="Found")
        assert r.passed is True

    def test_failed(self):
        r = AssertionResult(passed=False, name="contains:Party", detail="Not found")
        assert r.passed is False


class TestTurnResult:
    def test_all_pass(self):
        tr = TurnResult(
            turn=1,
            assertions=[
                AssertionResult(passed=True, name="a", detail="ok"),
                AssertionResult(passed=True, name="b", detail="ok"),
            ],
            passed=True,
            agent_message="result",
        )
        assert tr.passed is True

    def test_any_fail(self):
        tr = TurnResult(
            turn=1,
            assertions=[
                AssertionResult(passed=True, name="a", detail="ok"),
                AssertionResult(passed=False, name="b", detail="fail"),
            ],
            passed=False,
            agent_message="result",
        )
        assert tr.passed is False


class TestCostDelta:
    def test_ok(self):
        d = CostDelta(
            metric="input_tokens",
            baseline=3200,
            actual=3400,
            delta_pct=6.25,
            status="ok",
        )
        assert d.status == "ok"

    def test_warning(self):
        d = CostDelta(
            metric="input_tokens",
            baseline=3200,
            actual=4000,
            delta_pct=25.0,
            status="warning",
        )
        assert d.status == "warning"


class TestEvalCostSnapshot:
    def test_creation(self):
        s = EvalCostSnapshot(
            eval_name="test",
            agent="model-list-extractor",
            total_input_tokens=3200,
            total_output_tokens=600,
            total_cost_usd=0.008,
            total_latency_ms=4100,
            llm_calls=2,
            per_tool_tokens={"set_context_tool": 50},
            timestamp="2026-03-26T10:00:00Z",
        )
        assert s.total_cost_usd == 0.008


class TestEvalResult:
    def test_passed_summary(self):
        r = EvalResult(
            name="test eval",
            passed=True,
            turns=[
                TurnResult(
                    turn=1,
                    assertions=[AssertionResult(passed=True, name="a", detail="ok")],
                    passed=True,
                    agent_message="done",
                )
            ],
            cost_snapshot=None,
            cost_deltas=None,
        )
        summary = r.summary()
        assert "PASSED" in summary

    def test_failed_summary_includes_failures(self):
        r = EvalResult(
            name="test eval",
            passed=False,
            turns=[
                TurnResult(
                    turn=1,
                    assertions=[
                        AssertionResult(
                            passed=False, name="contains:Party", detail="Not found in response"
                        ),
                    ],
                    passed=False,
                    agent_message="done",
                )
            ],
            cost_snapshot=None,
            cost_deltas=None,
        )
        summary = r.summary()
        assert "FAILED" in summary
        assert "contains:Party" in summary

    def test_error_summary(self):
        r = EvalResult(
            name="test eval",
            passed=False,
            turns=[],
            cost_snapshot=None,
            cost_deltas=None,
            error="Agent raised ValueError",
        )
        summary = r.summary()
        assert "ValueError" in summary
