"""Result dataclasses for eval execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


@dataclass
class AgentOutput:
    """Structured output from an agent invocation."""

    messages: list[BaseMessage]
    structured_response: dict[str, Any] | None
    agent_name: str
    raw_state: dict[str, Any]


@dataclass
class AssertionResult:
    """Result of a single assertion check."""

    passed: bool
    name: str
    detail: str


@dataclass
class TurnResult:
    """Result of a single conversation turn."""

    turn: int
    assertions: list[AssertionResult]
    passed: bool
    agent_message: str | None
    structured_response: dict | list | None = None
    error: str | None = None


@dataclass
class CostDelta:
    """Comparison of a single metric against baseline."""

    metric: str
    baseline: float
    actual: float
    delta_pct: float
    status: str  # "ok" or "warning"


@dataclass
class EvalCostSnapshot:
    """Cost/latency data captured from a single eval run."""

    eval_name: str
    agent: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    llm_calls: int
    per_tool_tokens: dict[str, int]
    timestamp: str


@dataclass
class EvalResult:
    """Complete result of an eval case execution."""

    name: str
    passed: bool
    turns: list[TurnResult]
    cost_snapshot: EvalCostSnapshot | None
    cost_deltas: list[CostDelta] | None
    error: str | None = None

    def summary(self) -> str:
        """Human-readable summary for pytest failure output."""
        lines: list[str] = []
        status = "PASSED" if self.passed else "FAILED"
        lines.append(f"Eval: {self.name} — {status}")

        if self.error:
            lines.append(f"Error: {self.error}")

        lines.extend(
            f"  Turn {turn.turn} — {a.name}: {a.detail}"
            for turn in self.turns
            if not turn.passed
            for a in turn.assertions
            if not a.passed
        )

        if self.cost_deltas:
            warnings = [d for d in self.cost_deltas if d.status == "warning"]
            lines.extend(
                f"  Cost warning: {w.metric} {w.baseline} → {w.actual} ({w.delta_pct:+.1f}%)"
                for w in warnings
            )

        return "\n".join(lines)
