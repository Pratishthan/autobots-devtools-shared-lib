# ABOUTME: Posts eval assertion results as scores to Langfuse.
# ABOUTME: Enables eval result visualization alongside agent traces in Langfuse dashboard.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_client

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.eval.models.result import EvalResult

logger = logging.getLogger(__name__)


def post_scores(session_id: str, result: EvalResult) -> None:
    """Post eval results as scores to Langfuse.

    Args:
        session_id: The session ID linking to the Langfuse trace.
        result: The eval result to score.
    """
    client = get_langfuse_client()
    if client is None:
        logger.info("Langfuse not configured — skipping score posting")
        return

    try:
        # Fetch trace ID for this session
        traces_response = client.fetch_traces(session_id=session_id)  # type: ignore[attr-defined]
        traces = traces_response.data if traces_response else []
        if not traces:
            logger.warning("No trace found for session %s — skipping scoring", session_id)
            return

        trace_id = traces[0].id

        # Post overall eval score
        client.score(  # type: ignore[attr-defined]
            trace_id=trace_id,
            name=f"eval:{result.name}",
            value=1.0 if result.passed else 0.0,
            comment=result.summary(),
        )

        # Post per-assertion scores
        for turn in result.turns:
            for assertion in turn.assertions:
                client.score(  # type: ignore[attr-defined]
                    trace_id=trace_id,
                    name=f"eval:turn{turn.turn}:{assertion.name}",
                    value=1.0 if assertion.passed else 0.0,
                    comment=assertion.detail,
                )

        client.flush()

    except Exception:
        logger.exception("Failed to post scores to Langfuse for session %s", session_id)
