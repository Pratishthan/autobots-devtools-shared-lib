# ABOUTME: Dataclasses for cost analysis and token attribution.
# ABOUTME: ToolAttribution tracks per-tool token usage; CostReport aggregates across turns.

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolAttribution:
    """Token usage for a single tool call."""

    tool_name: str
    tool_input: str
    result_tokens: int
    utilization: float | None = None
    used_content_summary: str | None = None
    recommendation: str | None = None


@dataclass
class TokenAttribution:
    """Breakdown of input tokens by source for a single LLM call."""

    system_prompt_tokens: int
    conversation_history_tokens: int
    tool_result_tokens: int
    tools: list[ToolAttribution]
    overhead_tokens: int


@dataclass
class TurnCost:
    """Cost data for a single conversation turn."""

    turn: int
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    attribution: TokenAttribution


@dataclass
class CostReport:
    """Aggregate cost report for an entire eval run."""

    eval_name: str
    agent: str
    turns: list[TurnCost]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    llm_calls: int
    lowest_utilization_tools: list[ToolAttribution]
    recommendations: list[str]
