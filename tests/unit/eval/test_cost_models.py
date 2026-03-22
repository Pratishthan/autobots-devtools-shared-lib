# ABOUTME: Tests for cost analysis dataclasses.
# ABOUTME: Validates CostReport aggregation and ToolAttribution fields.

from autobots_devtools_shared_lib.eval.models.cost import (
    CostReport,
    TokenAttribution,
    ToolAttribution,
    TurnCost,
)


def test_tool_attribution_creation():
    t = ToolAttribution(
        tool_name="mer_read_file_tool(docs/file.md)",
        tool_input="docs/file.md",
        result_tokens=1900,
    )
    assert t.utilization is None
    assert t.recommendation is None


def test_turn_cost_with_attribution():
    attr = TokenAttribution(
        system_prompt_tokens=800,
        conversation_history_tokens=150,
        tool_result_tokens=2100,
        tools=[],
        overhead_tokens=150,
    )
    tc = TurnCost(
        turn=1,
        model="gemini-2.0-flash",
        input_tokens=3200,
        output_tokens=600,
        cost_usd=0.035,
        latency_ms=1200,
        attribution=attr,
    )
    assert tc.input_tokens == 3200


def test_cost_report_creation():
    report = CostReport(
        eval_name="test",
        agent="coordinator",
        turns=[],
        total_input_tokens=3200,
        total_output_tokens=600,
        total_cost_usd=0.035,
        total_latency_ms=1200,
        llm_calls=2,
        lowest_utilization_tools=[],
        recommendations=[],
    )
    assert report.total_cost_usd == 0.035
