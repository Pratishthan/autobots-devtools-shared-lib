"""Context store utilities: session resolution and CRUD operations."""

import json
from collections.abc import Mapping
from typing import Any

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.services import get_context_store

logger = get_logger(__name__)


def resolve_session_id(state: Mapping[str, Any]) -> str:
    """Resolve the session identifier from the given state.

    Args:
        state: Dict-like state containing optional 'session_id'.

    Returns:
        session_id string; 'default' if missing or invalid.
    """
    session_id = state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        logger.warning("Missing or invalid session_id in state; using 'default'")
        return "default"
    return session_id


def get_context(session_id: str) -> dict[str, Any]:
    """Load the current session context from the store.

    Args:
        session_id: Session identifier.

    Returns:
        JSON-serializable context dict; empty dict if none exists.
    """
    store = get_context_store()
    context = store.get(session_id) or {}
    logger.info(
        "Loaded context for session_id '%s' with keys: %s", session_id, list(context.keys())
    )
    return context


def set_context(session_id: str, data: dict[str, Any]) -> str:
    """Replace the session context with the provided data.

    Args:
        session_id: Session identifier.
        data: New context data.

    Returns:
        Success message.
    """
    store = get_context_store()
    store.set(session_id, data)
    logger.info("Set context for session_id '%s' with keys: %s", session_id, list(data.keys()))
    return "Context updated successfully."


def update_context(session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial update to the session context.

    Args:
        session_id: Session identifier.
        patch: Key-value updates to merge.

    Returns:
        The full context after the update.
    """
    store = get_context_store()
    updated = store.update(session_id, patch)
    logger.info(
        "Updated context for session_id '%s' with patch keys: %s; total keys now: %s",
        session_id,
        list(patch.keys()),
        list(updated.keys()),
    )
    return updated


def clear_context(session_id: str) -> str:
    """Clear any stored context for the session.

    Args:
        session_id: Session identifier.

    Returns:
        Success message.
    """
    store = get_context_store()
    store.delete(session_id)
    logger.info("Cleared context for session_id '%s'", session_id)
    return "Context cleared successfully."


def resolve_workspace_context_for_file_api(
    workspace_context: str, state: Mapping[str, Any] | None
) -> str:
    """Resolve workspace_context for file API when empty or '{}'.

    Uses state.get('workspace_context') if present, otherwise loads from context
    store using session_id from state. Returns a JSON string suitable for file
    API payloads.

    Args:
        workspace_context: Current value (e.g. from tool arg).
        state: Agent state dict; may be None if no runtime.

    Returns:
        JSON string for workspace context (never None; use '{}' when nothing found).
    """
    if workspace_context and workspace_context.strip() and workspace_context.strip() != "{}":
        return workspace_context
    if state is None:
        return workspace_context if workspace_context else "{}"
    from_state = state.get("workspace_context")
    if from_state is not None:
        if isinstance(from_state, dict):
            return json.dumps(from_state)
        if isinstance(from_state, str) and from_state.strip():
            return from_state
    session_id = resolve_session_id(state)
    context = get_context(session_id)
    if not context:
        return "{}"
    if "workspace_context" in context:
        val = context["workspace_context"]
        if isinstance(val, dict):
            return json.dumps(val)
        if isinstance(val, str) and val.strip():
            return val
    return json.dumps(context)
