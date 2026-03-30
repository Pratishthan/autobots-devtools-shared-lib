# ABOUTME: ProgressPersistenceMiddleware — mirrors agent todos to workspace_progress.
# ABOUTME: Uses a module-level callback so shared-lib stays decoupled from MER's DB.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware, AgentState

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.context_utils import get_context, resolve_context_key

if TYPE_CHECKING:
    from collections.abc import Callable

    from langgraph.runtime import Runtime

logger = get_logger(__name__)

# Module-level callback: (user_name, repo_name, jira_number, domain, stage, item, status, thread_id) -> None
_progress_callback: Callable[..., None] | None = None


def set_progress_callback(
    callback: Callable[..., None] | None,
) -> None:
    """Register the progress persistence callback.

    Called once at domain startup (e.g. in nurture/designer server.py) to wire
    update_progress() from MER into the shared-lib middleware.
    Pass None to clear.
    """
    global _progress_callback
    _progress_callback = callback


def get_progress_callback() -> Callable[..., None] | None:
    """Return the currently registered progress callback, or None."""
    return _progress_callback


class ProgressPersistenceMiddleware(AgentMiddleware):
    """Persist agent-level todos to workspace_progress (Postgres).

    Runs as an after_model hook: reads todos from state, resolves workspace
    identity via context store, and calls the registered progress callback.
    """

    def __init__(self, domain: str):
        self.domain = domain

    def after_model(self, state: AgentState[Any], runtime: Runtime[None]) -> dict[str, Any] | None:  # noqa: ARG002
        todos = state.get("todos")
        if not todos:
            return None

        if _progress_callback is None:
            logger.debug("No progress callback registered — skipping persistence")
            return None

        try:
            context_key = resolve_context_key(state)
            context = get_context(context_key)

            # Resolve thread_id from LangGraph config
            thread_id: str | None = None
            try:
                from langgraph.config import get_config

                config = get_config()
                thread_id = config.get("configurable", {}).get("thread_id")
            except Exception:
                logger.debug("Could not resolve thread_id from config", exc_info=True)

            agent_name = state.get("agent_name", "unknown")

            for todo in todos:
                _progress_callback(
                    user_name=context.get("user_name", ""),
                    repo_name=context.get("repo_name", ""),
                    jira_number=context.get("jira_number", ""),
                    domain=self.domain,
                    stage=agent_name,
                    item=todo.get("content", "unknown"),
                    status=todo.get("status", "pending"),
                    thread_id=thread_id,
                )
        except Exception:
            logger.warning("ProgressPersistenceMiddleware failed", exc_info=True)

        return None
