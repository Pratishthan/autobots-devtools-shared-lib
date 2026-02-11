from typing import Any

from langchain.tools import ToolRuntime, tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent
from autobots_devtools_shared_lib.dynagent.services import get_context_store

logger = get_logger(__name__)


def _get_session_id(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Resolve the session identifier from the current state."""
    session_id = runtime.state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        # Fallback to a deterministic default to avoid accidental cross-talk.
        logger.warning("Missing or invalid session_id in state; using 'default'")
        return "default"
    return session_id


@tool
def get_context(runtime: ToolRuntime[None, Dynagent]) -> dict[str, Any]:
    """Return the current session context as a JSON-serializable dict.

    The context is loaded from the configured ContextStore backend using the
    session_id found in the agent state. If no context exists yet, an empty
    dict is returned.
    """
    store = get_context_store()
    session_id = _get_session_id(runtime)
    context = store.get(session_id) or {}
    logger.info(
        "Loaded context for session_id '%s' with keys: %s", session_id, list(context.keys())
    )
    return context


@tool
def set_context(runtime: ToolRuntime[None, Dynagent], data: dict[str, Any]) -> str:
    """Replace the current session context with the provided data."""
    store = get_context_store()
    session_id = _get_session_id(runtime)
    store.set(session_id, data)
    logger.info("Set context for session_id '%s' with keys: %s", session_id, list(data.keys()))
    return "Context updated successfully."


@tool
def update_context(runtime: ToolRuntime[None, Dynagent], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial update to the session context and return the new context."""
    store = get_context_store()
    session_id = _get_session_id(runtime)
    updated = store.update(session_id, patch)
    logger.info(
        "Updated context for session_id '%s' with patch keys: %s; total keys now: %s",
        session_id,
        list(patch.keys()),
        list(updated.keys()),
    )
    return updated


@tool
def clear_context(runtime: ToolRuntime[None, Dynagent]) -> str:
    """Clear any stored context for the current session."""
    store = get_context_store()
    session_id = _get_session_id(runtime)
    store.delete(session_id)
    logger.info("Cleared context for session_id '%s'", session_id)
    return "Context cleared successfully."
