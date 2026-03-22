# ABOUTME: Pytest fixtures for the dynagent eval framework.
# ABOUTME: Provides dynagent_eval fixture that runs eval cases and collects results.

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.eval.core.cost_tracker import query_langfuse
from autobots_devtools_shared_lib.eval.core.runner import run_linear_eval
from autobots_devtools_shared_lib.eval.models.result import EvalResult
from autobots_devtools_shared_lib.eval.scoring.langfuse_scorer import post_scores

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from autobots_devtools_shared_lib.eval.models.eval_case import EvalCase


@pytest.fixture
def dynagent_eval(request: pytest.FixtureRequest):
    """Core eval fixture. Runs an EvalCase and returns EvalResult.

    Handles:
    - Session/thread ID generation
    - TraceMetadata creation with eval tags
    - Running the eval (linear mode in Phase 1)
    - Cost report collection (if tracking enabled)
    - Langfuse score posting (unless --eval-no-langfuse-score)
    """
    post_langfuse = not request.config.getoption("--eval-no-langfuse-score", default=False)

    async def run(eval_case: EvalCase) -> EvalResult:
        session_id = str(uuid.uuid4())
        config: RunnableConfig = {
            "configurable": {
                "thread_id": session_id,
                "agent_name": eval_case.agent,
            }
        }
        trace_metadata = TraceMetadata(
            session_id=session_id,
            app_name=f"eval-{eval_case.agent}",
            tags=["eval", *eval_case.tags],
        )

        if eval_case.mode == "linear":
            result = await run_linear_eval(eval_case, config, trace_metadata)
        else:
            # Goal mode added in Phase 3
            result = EvalResult(
                name=eval_case.name,
                passed=False,
                turns=[],
                cost_report=None,
                error="Goal-based mode not yet implemented (Phase 3)",
            )

        # Collect cost report
        if eval_case.cost.track:
            cost_report = query_langfuse(session_id)
            if cost_report:
                cost_report.eval_name = eval_case.name
                cost_report.agent = eval_case.agent
                result.cost_report = cost_report

        # Post scores to Langfuse
        if post_langfuse:
            post_scores(session_id, result)

        # Stash for session-level report
        if not hasattr(request.config, "_eval_cost_reports"):
            request.config._eval_cost_reports = []  # type: ignore[attr-defined]
        request.config._eval_cost_reports.append(result)  # type: ignore[attr-defined]

        return result

    return run
