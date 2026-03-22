# ABOUTME: Level 1 cost tracker that queries Langfuse for token attribution.
# ABOUTME: Extracts per-turn token counts, costs, and tool-level breakdown from trace spans.

from __future__ import annotations

import logging

from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_client
from autobots_devtools_shared_lib.eval.models.cost import (
    CostReport,
    TokenAttribution,
    ToolAttribution,
    TurnCost,
)

logger = logging.getLogger(__name__)


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


def query_langfuse(session_id: str, partial: bool = False) -> CostReport | None:
    """Query Langfuse for trace data and build a Level 1 cost report.

    Args:
        session_id: The session ID used during the eval run.
        partial: If True, tolerate missing data (for error cases).

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
