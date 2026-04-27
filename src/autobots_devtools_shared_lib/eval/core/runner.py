# ABOUTME: Eval runner that drives agent conversations and collects assertion results.
# ABOUTME: Supports linear mode (Phase 1). Goal-based mode added in Phase 3.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from autobots_devtools_shared_lib.dynagent.agents.invocation_utils import ainvoke_agent
from autobots_devtools_shared_lib.eval.assertions.registry import resolve_assertion
from autobots_devtools_shared_lib.eval.core.workspace import resolve_eval_state_schema
from autobots_devtools_shared_lib.eval.models.result import (
    AgentOutput,
    AssertionResult,
    EvalResult,
    TurnResult,
)

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import RunnableConfig

    from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
    from autobots_devtools_shared_lib.eval.models.eval_case import EvalCase

logger = logging.getLogger(__name__)


def _extract_last_ai_content(messages: list[BaseMessage]) -> str | None:
    """Get text content of the last AI message."""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return str(msg.content)
    return None


def _build_agent_output(result: dict[str, Any]) -> AgentOutput:
    """Convert invoke_agent result dict to AgentOutput."""
    return AgentOutput(
        messages=result.get("messages", []),
        structured_response=result.get("structured_response"),
        agent_name=result.get("agent_name", ""),
        raw_state=result,
    )


def _run_assertions(
    agent_output: AgentOutput,
    assertions: list[Any],
    retry_count: int = 0,
    retry_only_for: list[str] | None = None,
) -> list[AssertionResult]:
    """Run all assertions against an agent output, with optional retry for flaky assertions."""
    results: list[AssertionResult] = []
    retry_names = set(retry_only_for) if retry_only_for else set()

    for assertion in assertions:
        try:
            eval_fn = resolve_assertion(assertion.name)
            result = eval_fn(agent_output, assertion.config)

            # Retry logic: retry failed assertions if eligible.
            if not result.passed and retry_count > 0 and assertion.name in retry_names:
                for attempt in range(retry_count):
                    logger.info(
                        "Retrying %s (attempt %d/%d)", assertion.name, attempt + 1, retry_count
                    )
                    result = eval_fn(agent_output, assertion.config)
                    if result.passed:
                        break

            results.append(result)
        except Exception as e:
            results.append(
                AssertionResult(
                    passed=False,
                    name=assertion.name,
                    detail=f"Assertion error: {type(e).__name__}: {e}",
                )
            )
    return results


async def run_linear_eval(
    eval_case: EvalCase,
    config: RunnableConfig,
    trace_metadata: TraceMetadata | None,
) -> EvalResult:
    """Execute a linear eval: replay turns, run assertions after each."""
    turns: list[TurnResult] = []

    if not eval_case.turns:
        return EvalResult(
            name=eval_case.name,
            passed=False,
            turns=[],
            cost_snapshot=None,
            cost_deltas=None,
            error="No turns defined",
        )

    for turn_num, turn in enumerate(eval_case.turns, start=1):
        try:
            input_state: dict[str, Any] = {
                "messages": [{"role": "user", "content": turn.user}],
                **eval_case.state,
            }

            result = await ainvoke_agent(
                agent_name=eval_case.agent,
                input_state=input_state,
                config=config,
                enable_tracing=trace_metadata is not None,
                trace_metadata=trace_metadata,
                state_schema=resolve_eval_state_schema(),
            )

            agent_output = _build_agent_output(result)
            assertion_results = _run_assertions(
                agent_output,
                turn.assertions,
                retry_count=eval_case.retry.count,
                retry_only_for=eval_case.retry.only_for,
            )
            all_passed = all(a.passed for a in assertion_results)

            turns.append(
                TurnResult(
                    turn=turn_num,
                    assertions=assertion_results,
                    passed=all_passed,
                    agent_message=_extract_last_ai_content(agent_output.messages),
                )
            )

        except Exception as e:
            logger.exception("Agent invocation failed on turn %d", turn_num)
            turns.append(
                TurnResult(
                    turn=turn_num,
                    assertions=[],
                    passed=False,
                    agent_message=None,
                    error=f"Agent error: {type(e).__name__}: {e}",
                )
            )
            return EvalResult(
                name=eval_case.name,
                passed=False,
                turns=turns,
                cost_snapshot=None,
                cost_deltas=None,
                error=str(e),
            )

    all_turns_passed = all(t.passed for t in turns)
    return EvalResult(
        name=eval_case.name,
        passed=all_turns_passed,
        turns=turns,
        cost_snapshot=None,  # Cost tracking wired in pytest fixture
        cost_deltas=None,
    )
