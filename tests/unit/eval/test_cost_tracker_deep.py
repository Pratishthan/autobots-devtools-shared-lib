# ABOUTME: Tests for Level 2 cost utilization analysis.
# ABOUTME: Validates LLM-based tool utilization scoring with mocked judge.

from __future__ import annotations

from unittest.mock import MagicMock, patch

from autobots_devtools_shared_lib.eval.core.cost_tracker import analyze_tool_utilization
from autobots_devtools_shared_lib.eval.models.cost import ToolAttribution


def test_analyze_skips_small_tool_results():
    """Tool results under 50 tokens are skipped (not worth analyzing)."""
    attr = ToolAttribution(
        tool_name="get_context",
        tool_input="key",
        result_tokens=30,
    )
    result = analyze_tool_utilization(attr, agent_output_text="Used the context")
    assert result.utilization is None
    assert result.recommendation is None


def test_analyze_auto_flags_huge_results():
    """Tool results over 10000 tokens are auto-flagged without judge call."""
    attr = ToolAttribution(
        tool_name="mer_read_file_tool(huge_file.md)",
        tool_input="huge_file.md",
        result_tokens=12000,
    )
    result = analyze_tool_utilization(attr, agent_output_text="Used a small part")
    assert result.utilization is not None
    assert result.utilization < 0.1
    assert result.recommendation is not None
    assert "too large" in result.recommendation.lower() or "12000" in result.recommendation


def test_analyze_calls_judge_for_medium_results():
    """Tool results between 50 and 10000 tokens are sent to the judge."""
    mock_evaluator = MagicMock(
        return_value={
            "score": 0.3,
            "reasoning": "Agent only used model names from a large document",
        }
    )
    with patch(
        "autobots_devtools_shared_lib.eval.core.cost_tracker.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        attr = ToolAttribution(
            tool_name="mer_read_file_tool(feature_lld.md)",
            tool_input="feature_lld.md",
            result_tokens=1900,
        )
        result = analyze_tool_utilization(
            attr,
            agent_output_text="Found models: Party, Address, Contact",
            tool_result_text="Long LLD document content here...",
        )
        assert result.utilization == 0.3
        assert result.used_content_summary is not None


def test_analyze_no_recommendation_for_high_utilization():
    """High utilization tools get no recommendation."""
    mock_evaluator = MagicMock(
        return_value={
            "score": 0.9,
            "reasoning": "Agent used most of the content",
        }
    )
    with patch(
        "autobots_devtools_shared_lib.eval.core.cost_tracker.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        attr = ToolAttribution(
            tool_name="set_context_tool",
            tool_input="data",
            result_tokens=100,
        )
        result = analyze_tool_utilization(
            attr,
            agent_output_text="Used all the context data",
            tool_result_text="Context data...",
        )
        assert result.utilization == 0.9
        assert result.recommendation is None


def test_analyze_judge_error_returns_unchanged():
    """If the judge fails, return the attribution unchanged."""
    mock_evaluator = MagicMock(side_effect=RuntimeError("Judge failed"))
    with patch(
        "autobots_devtools_shared_lib.eval.core.cost_tracker.create_llm_as_judge",
        return_value=mock_evaluator,
    ):
        attr = ToolAttribution(
            tool_name="mer_read_file_tool",
            tool_input="file.md",
            result_tokens=500,
        )
        result = analyze_tool_utilization(
            attr,
            agent_output_text="Output",
            tool_result_text="File content",
        )
        assert result.utilization is None
        assert result.recommendation is None
