# ABOUTME: Factory function make_dynagent_eval for the dynagent eval pytest fixture.
# ABOUTME: Handles workspace staging, runner dispatch, cost tracking, and teardown.

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata
from autobots_devtools_shared_lib.eval.core.cost_tracker import query_langfuse_cost
from autobots_devtools_shared_lib.eval.core.runner import run_linear_eval
from autobots_devtools_shared_lib.eval.core.workspace import setup_workspace, teardown_workspace
from autobots_devtools_shared_lib.eval.models.result import EvalResult
from autobots_devtools_shared_lib.eval.scoring.langfuse_scorer import post_scores

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from langchain_core.runnables import RunnableConfig

    from autobots_devtools_shared_lib.eval.models.eval_case import EvalCase

logger = logging.getLogger(__name__)


def make_dynagent_eval(
    *,
    update_golden: bool,
    update_baseline: bool,
    no_langfuse_score: bool,
) -> Callable[[EvalCase], Coroutine[Any, Any, EvalResult]]:
    """Factory that returns an async callable to run a single eval case.

    The returned callable handles:
    - Session/thread ID generation
    - Workspace setup/teardown
    - Running the eval via run_linear_eval
    - Cost tracking via query_langfuse_cost
    - Langfuse score posting (unless no_langfuse_score)
    - Golden output update (when update_golden=True)

    Args:
        update_golden: Whether to update golden output files.
        update_baseline: Whether to save cost snapshots as new baselines.
        no_langfuse_score: If True, skip posting scores to Langfuse.

    Returns:
        An async callable that takes an EvalCase and returns an EvalResult.
    """

    async def _eval(eval_case: EvalCase) -> EvalResult:
        session_id = str(uuid.uuid4())
        workspace_path = "/Users/shruthi/Projects/workspace/khushboo-2802394_infosys/fbp-core-genai-sanity-MER-9999"

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

        try:
            # Stage workspace files
            setup_workspace(eval_case.setup, workspace_path)

            # Run the eval
            if eval_case.mode == "linear":
                result = await run_linear_eval(eval_case, config, trace_metadata)
            else:
                result = EvalResult(
                    name=eval_case.name,
                    passed=False,
                    turns=[],
                    cost_snapshot=None,
                    cost_deltas=None,
                    error="Goal-based mode not yet implemented (Phase 3)",
                )

            # Cost tracking
            if eval_case.cost.track:
                snapshot = query_langfuse_cost(session_id, eval_case.name, eval_case.agent)
                if snapshot is not None:
                    result.cost_snapshot = snapshot

            # Golden output update (placeholder — save function not yet implemented)
            if update_golden:
                logger.info("update_golden requested for %s (not yet implemented)", eval_case.name)

            # Baseline update (placeholder — CostConfig only has track: bool)
            if update_baseline and result.cost_snapshot is not None:
                logger.info(
                    "update_baseline requested for %s (no baseline path in CostConfig)",
                    eval_case.name,
                )

            # Post scores to Langfuse
            if not no_langfuse_score:
                post_scores(session_id, result)

        finally:
            teardown_workspace(workspace_path)

        return result

    return _eval
