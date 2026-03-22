# ABOUTME: Dataclasses for eval execution results.
# ABOUTME: AgentOutput wraps invoke_agent output; AssertionResult/TurnResult/EvalResult track pass/fail.

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

    from autobots_devtools_shared_lib.eval.models.cost import CostReport


@dataclass
class AgentOutput:
    """Normalized output from invoke_agent for assertion evaluation."""

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
    inconclusive: bool = False


@dataclass
class TurnResult:
    """Result of all assertions for a single conversation turn."""

    turn: int
    assertions: list[AssertionResult]
    passed: bool
    agent_message: str | None
    error: str | None = None


@dataclass
class EvalResult:
    """Overall result of an eval case execution."""

    name: str
    passed: bool
    turns: list[TurnResult]
    cost_report: CostReport | None
    termination_reason: str | None = None
    error: str | None = None

    def summary(self) -> str:
        """Human-readable summary for pytest failure output."""
        lines = [f"Eval: {self.name}"]
        status = "PASSED" if self.passed else "FAILED"
        lines.append(f"Status: {status}")

        if self.error:
            lines.append(f"Error: {self.error}")

        for turn in self.turns:
            if not turn.passed:
                lines.append(f"  Turn {turn.turn}:")
                for a in turn.assertions:
                    if not a.passed:
                        flag = " (inconclusive)" if a.inconclusive else ""
                        lines.append(f"    FAIL {a.name}: {a.detail}{flag}")

        return "\n".join(lines)
