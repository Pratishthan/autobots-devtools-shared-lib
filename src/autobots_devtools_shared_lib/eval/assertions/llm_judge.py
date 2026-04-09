# ABOUTME: LLM-as-judge assertion functions wrapping OpenEvals.
# ABOUTME: Evaluates free-text agent responses against criteria using an LLM judge.

from __future__ import annotations

import logging
from typing import Any

from openevals.llm import create_llm_as_judge  # pyright: ignore[reportMissingImports]

from autobots_devtools_shared_lib.eval.models.result import AgentOutput, AssertionResult

logger = logging.getLogger(__name__)

# Default judge model — cheap and fast for evaluation
_DEFAULT_JUDGE_MODEL = "google_genai/gemini-2.0-flash"

_LLM_JUDGE_PROMPT = """You are evaluating an AI agent's response.

Criteria: {criteria}

Agent response:
{outputs}

Rate how well the response meets the criteria on a scale from 0.0 to 1.0."""


def _last_ai_content(agent_output: AgentOutput) -> str:
    """Extract text content from the last AI message."""
    for msg in reversed(agent_output.messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return str(msg.content)
    return ""


def llm_judge(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Evaluate agent response against criteria using an LLM judge.

    Config can be:
      - str: criteria string (threshold defaults to 0.5)
      - dict: {"criteria": str, "threshold": float, "model": str (optional)}
    """
    if isinstance(config, str):
        criteria = config
        threshold = 0.5
        model = _DEFAULT_JUDGE_MODEL
    elif isinstance(config, dict):
        criteria = config.get("criteria", "")
        threshold = config.get("threshold", 0.5)
        model = config.get("model", _DEFAULT_JUDGE_MODEL)
    else:
        return AssertionResult(
            passed=False,
            name="llm_judge",
            detail=f"Invalid config type: {type(config).__name__}",
        )

    if not criteria:
        return AssertionResult(
            passed=False,
            name="llm_judge",
            detail="No criteria specified",
        )

    agent_text = _last_ai_content(agent_output)

    try:
        evaluator = create_llm_as_judge(
            prompt=_LLM_JUDGE_PROMPT,
            model=model,
            continuous=True,
            feedback_key="score",
        )

        result = evaluator(
            outputs=agent_text,
            criteria=criteria,
        )

        # result is a list[EvaluatorResult]; take the first entry
        first = result[0] if isinstance(result, list) else result
        score = float(first["score"]) if isinstance(first, dict) else float(first.score)
        comment = first.get("comment") or "" if isinstance(first, dict) else (first.comment or "")
        passed = score >= threshold

        return AssertionResult(
            passed=passed,
            name="llm_judge",
            detail=f"Score: {score:.2f} (threshold: {threshold}). {comment}",
        )

    except Exception as e:
        logger.warning("LLM judge failed: %s", e)
        return AssertionResult(
            passed=False,
            name="llm_judge",
            detail=f"Judge error: {type(e).__name__}: {e}",
        )


_TRAJECTORY_PROMPT = """You are evaluating an AI agent's tool usage trajectory.

Criteria: {criteria}

Full conversation (messages and tool calls):
{outputs}

Rate how well the agent's tool usage meets the criteria on a scale from 0.0 to 1.0.
Consider: Were tools used efficiently? Were there redundant calls? Was the sequence logical?"""


def _format_trajectory(agent_output: AgentOutput) -> str:
    """Format the full message history including tool calls for the judge."""
    lines: list[str] = []
    for msg in agent_output.messages:
        msg_type = getattr(msg, "type", "unknown")
        content = str(msg.content) if msg.content else ""

        if msg_type == "human":
            lines.append(f"[User]: {content}")
        elif msg_type == "ai":
            lines.append(f"[Agent]: {content}")
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        lines.append(f"  -> Tool call: {tc.get('name', '?')}({tc.get('args', {})})")
                    elif hasattr(tc, "name"):
                        lines.append(f"  -> Tool call: {tc.name}({getattr(tc, 'args', {})})")
        elif msg_type == "tool":
            tool_name = getattr(msg, "name", "?")
            lines.append(f"[Tool result ({tool_name})]: {content[:200]}...")
    return "\n".join(lines)


def trajectory_quality(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Evaluate the quality of an agent's tool usage trajectory.

    Config: {"criteria": str, "threshold": float (default 0.5), "model": str (optional)}
    """
    if isinstance(config, str):
        criteria = config
        threshold = 0.5
        model = _DEFAULT_JUDGE_MODEL
    elif isinstance(config, dict):
        criteria = config.get("criteria", "")
        threshold = config.get("threshold", 0.5)
        model = config.get("model", _DEFAULT_JUDGE_MODEL)
    else:
        return AssertionResult(
            passed=False,
            name="trajectory_quality",
            detail=f"Invalid config type: {type(config).__name__}",
        )

    if not criteria:
        return AssertionResult(
            passed=False,
            name="trajectory_quality",
            detail="No criteria specified",
        )

    trajectory_text = _format_trajectory(agent_output)

    try:
        evaluator = create_llm_as_judge(
            prompt=_TRAJECTORY_PROMPT,
            model=model,
            continuous=True,
            feedback_key="score",
        )

        result = evaluator(
            outputs=trajectory_text,
            criteria=criteria,
        )

        # result is a list[EvaluatorResult]; take the first entry
        first = result[0] if isinstance(result, list) else result
        score = float(first["score"]) if isinstance(first, dict) else float(first.score)
        comment = first.get("comment") or "" if isinstance(first, dict) else (first.comment or "")
        passed = score >= threshold

        return AssertionResult(
            passed=passed,
            name="trajectory_quality",
            detail=f"Score: {score:.2f} (threshold: {threshold}). {comment}",
        )

    except Exception as e:
        logger.warning("Trajectory quality judge failed: %s", e)
        return AssertionResult(
            passed=False,
            name="trajectory_quality",
            detail=f"Judge error: {type(e).__name__}: {e}",
        )
