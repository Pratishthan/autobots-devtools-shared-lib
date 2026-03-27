# ABOUTME: Cost report generation for eval results.
# ABOUTME: Writes JSON reports and formats terminal summaries.

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.eval.models.result import EvalResult

logger = logging.getLogger(__name__)


def write_cost_report(path: str, results: list[EvalResult]) -> None:
    """Write eval cost report as JSON."""
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total_cost = sum(r.cost_snapshot.total_cost_usd for r in results if r.cost_snapshot)
    total_tokens = sum(
        r.cost_snapshot.total_input_tokens + r.cost_snapshot.total_output_tokens
        for r in results
        if r.cost_snapshot
    )

    report = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "summary": {
            "total_evals": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
        },
        "evals": [],
    }

    for r in results:
        eval_entry: dict = {
            "name": r.name,
            "passed": r.passed,
        }
        if r.cost_snapshot:
            eval_entry["cost"] = {
                "total_input_tokens": r.cost_snapshot.total_input_tokens,
                "total_output_tokens": r.cost_snapshot.total_output_tokens,
                "total_cost_usd": round(r.cost_snapshot.total_cost_usd, 6),
                "llm_calls": r.cost_snapshot.llm_calls,
            }
        report["evals"].append(eval_entry)

    report_path.write_text(json.dumps(report, indent=2))
    logger.info("Cost report written to %s", path)


def format_terminal_summary(results: list[EvalResult]) -> str:
    """Format a terminal-friendly cost summary."""
    has_cost = any(r.cost_snapshot for r in results)
    if not has_cost:
        return ""

    total_cost = sum(r.cost_snapshot.total_cost_usd for r in results if r.cost_snapshot)
    total_evals = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total_evals - passed

    lines = [
        "",
        "=" * 60,
        f" Eval cost summary: ${total_cost:.4f} across {total_evals} evals"
        f" ({passed} passed, {failed} failed)",
        "=" * 60,
    ]

    lines.append("=" * 60)
    return "\n".join(lines)
