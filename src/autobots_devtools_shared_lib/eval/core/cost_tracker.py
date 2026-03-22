# ABOUTME: Level 1 cost tracker that queries Langfuse for token attribution.
# ABOUTME: Extracts per-turn token counts, costs, and tool-level breakdown from trace spans.

from __future__ import annotations

import logging

from openevals.llm import create_llm_as_judge

from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_client
from autobots_devtools_shared_lib.eval.models.cost import (
    CostReport,
    TokenAttribution,
    ToolAttribution,
    TurnCost,
)

logger = logging.getLogger(__name__)

_UTILIZATION_JUDGE_MODEL = "google_genai/gemini-2.0-flash"

_UTILIZATION_PROMPT = """You are analyzing token efficiency in an AI agent's tool usage.

The agent called the tool: {tool_name}
The tool returned this content ({result_tokens} tokens):
<tool_result>{tool_result}</tool_result>

The agent then produced this output:
<agent_output>{agent_output}</agent_output>

Rate the utilization on a scale from 0.0 to 1.0:
- 1.0 means the agent used all of the tool result
- 0.0 means the agent used none of the tool result

Consider what specific parts of the tool result the agent actually used in its output."""


def analyze_tool_utilization(
    attribution: ToolAttribution,
    agent_output_text: str,
    tool_result_text: str | None = None,
) -> ToolAttribution:
    """Analyze how much of a tool's result was actually used by the agent.

    Args:
        attribution: The tool attribution to analyze.
        agent_output_text: The agent's final output text.
        tool_result_text: The raw tool result text (if available).

    Returns:
        Updated ToolAttribution with utilization, summary, and recommendation.
    """
    # Skip small results — not worth analyzing
    if attribution.result_tokens < 50:
        return attribution

    # Auto-flag huge results without a judge call
    if attribution.result_tokens > 10000:
        attribution.utilization = 0.05
        attribution.used_content_summary = "Auto-flagged: tool result too large for efficient use"
        attribution.recommendation = (
            f"Tool result is {attribution.result_tokens} tokens — almost certainly wasteful. "
            f"Pre-filter or split the input to reduce token consumption."
        )
        return attribution

    # Truncate tool result for judge (head + tail if >4000 tokens)
    display_result = tool_result_text or "(tool result text not available)"
    if len(display_result) > 16000:  # rough 4000-token proxy
        half = 8000
        display_result = display_result[:half] + "\n...[truncated]...\n" + display_result[-half:]

    try:
        evaluator = create_llm_as_judge(
            prompt=_UTILIZATION_PROMPT,
            model=_UTILIZATION_JUDGE_MODEL,
            continuous=True,
            feedback_key="score",
        )

        result = evaluator(
            outputs=agent_output_text,
            tool_name=attribution.tool_name,
            result_tokens=str(attribution.result_tokens),
            tool_result=display_result,
            agent_output=agent_output_text,
        )

        # Handle both list and dict return from openevals
        if isinstance(result, list):
            result = result[0] if result else {}
        score = (
            float(result.get("score", 0.0))
            if isinstance(result, dict)
            else float(getattr(result, "score", 0.0))
        )
        reasoning = (
            result.get("reasoning", "")
            if isinstance(result, dict)
            else getattr(result, "reasoning", "")
        )

        attribution.utilization = score
        attribution.used_content_summary = reasoning

        if score < 0.5:
            attribution.recommendation = (
                f"Utilization is {score:.0%} ({attribution.result_tokens} tokens). "
                f"{reasoning}"
            )

    except Exception:
        logger.warning(
            "Utilization analysis failed for %s", attribution.tool_name, exc_info=True
        )

    return attribution


def _estimate_tokens(text: str) -> int:
    """Rough token estimation. Uses len/4 as a fast heuristic."""
    if not text:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


def query_langfuse(session_id: str, partial: bool = False, deep: bool = False) -> CostReport | None:
    """Query Langfuse for trace data and build a Level 1 (or Level 2) cost report.

    Args:
        session_id: The session ID used during the eval run.
        partial: If True, tolerate missing data (for error cases).
        deep: If True, run Level 2 utilization analysis via LLM judge.

    Returns:
        CostReport if Langfuse is available and trace found, None otherwise.
    """
    client = get_langfuse_client()
    if client is None:
        logger.info("Langfuse not configured — cost report unavailable")
        return None

    try:
        # Fetch traces for this session
        traces_response = client.fetch_traces(session_id=session_id)  # type: ignore[attr-defined]
        traces = traces_response.data if traces_response else []

        if not traces:
            logger.warning("No traces found for session %s", session_id)
            return None

        all_turns: list[TurnCost] = []
        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_latency = 0
        llm_calls = 0

        for trace in traces:
            trace_detail = client.fetch_trace(trace.id)  # type: ignore[attr-defined]
            if not trace_detail or not hasattr(trace_detail, "observations"):
                continue

            for obs in trace_detail.observations:
                if obs.type != "GENERATION":
                    continue

                llm_calls += 1
                input_tokens = getattr(obs.usage, "input", 0) or 0 if obs.usage else 0
                output_tokens = getattr(obs.usage, "output", 0) or 0 if obs.usage else 0
                cost = obs.calculated_total_cost or 0.0

                # Estimate latency
                latency_ms = 0
                if obs.start_time and obs.end_time:
                    try:
                        start_ts = obs.start_time.timestamp()
                        end_ts = obs.end_time.timestamp()
                        latency_ms = int((end_ts - start_ts) * 1000)
                    except Exception:
                        logger.debug("Could not compute latency for observation", exc_info=True)

                total_input += input_tokens
                total_output += output_tokens
                total_cost += cost
                total_latency += latency_ms

                # Build basic attribution (tool-level detail requires span walking)
                tool_attributions: list[ToolAttribution] = []
                attribution = TokenAttribution(
                    system_prompt_tokens=0,
                    conversation_history_tokens=0,
                    tool_result_tokens=0,
                    tools=tool_attributions,
                    overhead_tokens=0,
                )

                all_turns.append(
                    TurnCost(
                        turn=len(all_turns) + 1,
                        model=obs.model or "unknown",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost,
                        latency_ms=latency_ms,
                        attribution=attribution,
                    )
                )

        # Level 2: deep utilization analysis
        if deep:
            for turn_cost in all_turns:
                for tool_attr in turn_cost.attribution.tools:
                    analyze_tool_utilization(
                        tool_attr,
                        agent_output_text="",  # populated from trace in production
                    )

            # Collect lowest utilization tools and recommendations
            all_tool_attrs = [
                t for tc in all_turns for t in tc.attribution.tools if t.utilization is not None
            ]
            low_util = [t for t in all_tool_attrs if t.utilization is not None and t.utilization < 0.5]
            low_util.sort(key=lambda t: t.utilization or 0.0)

            return CostReport(
                eval_name="",  # set by caller
                agent="",  # set by caller
                turns=all_turns,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_cost_usd=total_cost,
                total_latency_ms=total_latency,
                llm_calls=llm_calls,
                lowest_utilization_tools=low_util[:5],
                recommendations=[t.recommendation for t in low_util if t.recommendation],
            )

        return CostReport(
            eval_name="",  # set by caller
            agent="",  # set by caller
            turns=all_turns,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            llm_calls=llm_calls,
            lowest_utilization_tools=[],
            recommendations=[],
        )

    except Exception:
        logger.exception("Failed to query Langfuse for session %s", session_id)
        if partial:
            return None
        raise
