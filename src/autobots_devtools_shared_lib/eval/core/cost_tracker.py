# ABOUTME: Cost tracking for eval runs: Langfuse query, baseline comparison, snapshot persistence.
# ABOUTME: Provides load_baseline, save_baseline, compare_with_baseline, and query_langfuse_cost.
"""Cost tracking: Langfuse query, baseline comparison, snapshot persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autobots_devtools_shared_lib.eval.models.result import CostDelta, EvalCostSnapshot

logger = logging.getLogger(__name__)

# Metric mapping: threshold key → snapshot field
_METRIC_MAP: dict[str, str] = {
    "input_tokens": "total_input_tokens",
    "output_tokens": "total_output_tokens",
    "cost_usd": "total_cost_usd",
    "latency_ms": "total_latency_ms",
    "llm_calls": "llm_calls",
}


def query_langfuse_cost(session_id: str, eval_name: str, agent: str) -> EvalCostSnapshot | None:
    """Query Langfuse for cost data from an eval run.

    Returns None if Langfuse is unavailable or no traces found.
    """
    try:
        from autobots_devtools_shared_lib.common.observability.tracing import (
            get_langfuse_client,
        )

        client = get_langfuse_client()
        if not client:
            logger.warning("Langfuse client unavailable, skipping cost tracking")
            return None

        traces = client.fetch_traces(session_id=session_id)  # pyright: ignore[reportAttributeAccessIssue]
        if not traces.data:
            logger.warning("No traces found for session_id=%s", session_id)
            return None

        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_latency = 0
        llm_calls = 0
        per_tool: dict[str, int] = {}

        for trace in traces.data:
            observations = client.fetch_observations(trace_id=trace.id)  # pyright: ignore[reportAttributeAccessIssue]
            for obs in observations.data:
                if obs.type == "GENERATION":
                    llm_calls += 1
                    if obs.usage:
                        total_input += obs.usage.input or 0
                        total_output += obs.usage.output or 0
                    if obs.calculated_total_cost:
                        total_cost += obs.calculated_total_cost
                    if obs.latency:
                        total_latency += int(obs.latency * 1000)
                elif obs.type == "SPAN" and obs.name:
                    if obs.usage and obs.usage.input:
                        per_tool[obs.name] = obs.usage.input

        return EvalCostSnapshot(
            eval_name=eval_name,
            agent=agent,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=round(total_cost, 6),
            total_latency_ms=total_latency,
            llm_calls=llm_calls,
            per_tool_tokens=per_tool,
            timestamp=datetime.now(UTC).isoformat(),
        )

    except Exception:
        logger.exception("Failed to query Langfuse for cost data")
        return None


def load_baseline(path: str) -> dict[str, Any] | None:
    """Load a cost baseline JSON file. Returns None if file doesn't exist."""
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save_baseline(snapshot: EvalCostSnapshot, path: str) -> None:
    """Save a cost snapshot as a baseline JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(snapshot)
    data.pop("timestamp", None)
    p.write_text(json.dumps(data, indent=2) + "\n")


def compare_with_baseline(
    snapshot: EvalCostSnapshot,
    baseline: dict[str, Any],
    thresholds: dict[str, float],
) -> list[CostDelta]:
    """Compare a snapshot against a baseline, returning deltas with status.

    A delta is "warning" only if the actual value INCREASED beyond the threshold percentage.
    Decreases are always "ok".
    """
    deltas: list[CostDelta] = []

    for threshold_key, field_name in _METRIC_MAP.items():
        actual = getattr(snapshot, field_name, 0)
        baseline_val = baseline.get(field_name, 0)

        if baseline_val == 0:
            delta_pct = 0.0 if actual == 0 else 100.0
        else:
            delta_pct = ((actual - baseline_val) / baseline_val) * 100

        threshold = thresholds.get(threshold_key)
        status = "warning" if threshold is not None and delta_pct > threshold else "ok"

        deltas.append(
            CostDelta(
                metric=threshold_key,
                baseline=baseline_val,
                actual=actual,
                delta_pct=round(delta_pct, 1),
                status=status,
            )
        )

    return deltas
