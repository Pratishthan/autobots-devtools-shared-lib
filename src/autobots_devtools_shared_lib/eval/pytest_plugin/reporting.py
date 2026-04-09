# ABOUTME: Cost reporting for eval runs: terminal summary and JSON file output.
# ABOUTME: Provides format_cost_summary and write_cost_report for session-end reporting.
"""Cost reporting: terminal summary and JSON report generation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.eval.models.result import EvalResult


def format_cost_summary(results: list[EvalResult]) -> str:
    """Format cost comparison as terminal output."""
    results_with_cost = [r for r in results if r.cost_snapshot is not None]
    if not results_with_cost:
        return "No cost data collected."

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(" eval cost comparison")
    lines.append("=" * 60)

    for r in results_with_cost:
        snap = r.cost_snapshot
        assert snap is not None
        lines.append(f"\n{snap.agent} ({r.name}):")

        if r.cost_deltas:
            for d in r.cost_deltas:
                warn = " ⚠ warning" if d.status == "warning" else ""
                lines.append(f"  {d.metric}: {d.baseline} → {d.actual} ({d.delta_pct:+.1f}%){warn}")
        else:
            lines.append(f"  Input tokens:  {snap.total_input_tokens}")
            lines.append(f"  Output tokens: {snap.total_output_tokens}")
            lines.append(f"  Cost:          ${snap.total_cost_usd:.4f}")
            lines.append(f"  Latency:       {snap.total_latency_ms}ms")
            lines.append(f"  LLM calls:     {snap.llm_calls}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def write_cost_report(results: list[EvalResult], path: str) -> None:
    """Write cost report as JSON file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "evals": [],
    }

    for r in results:
        entry: dict = {
            "name": r.name,
            "passed": r.passed,
        }
        if r.cost_snapshot:
            entry["agent"] = r.cost_snapshot.agent
            entry["cost"] = asdict(r.cost_snapshot)
        if r.cost_deltas:
            entry["deltas"] = [asdict(d) for d in r.cost_deltas]
        report["evals"].append(entry)

    p.write_text(json.dumps(report, indent=2) + "\n")
