"""Context store utilities: session resolution and CRUD operations.

Use-case apps can plug in custom context key formation by calling
set_context_key_resolver() at startup. Context payload keys (e.g. component,
version, last_section) are defined by the use case: use set_context/update_context
with any dict shape; formation logic can live in use-case tools that call these
helpers or the shared context tools.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.services import get_context_store

logger = get_logger(__name__)

# Use-case-provided resolver: (state) -> context_key. None = use default logic.
_context_key_resolver: Callable[[Mapping[str, Any]], str] | None = None


def set_context_key_resolver(
    resolver: Callable[[Mapping[str, Any]], str] | None,
) -> None:
    """Set a use-case-level function to derive the context key from agent state.

    When set, resolve_context_key(state) will call this instead of using
    state.get('context_key', 'default'). Pass None to restore default behavior.

    Example (e.g. in bro usecase_ui.py at startup):
        from autobots_devtools_shared_lib.common.utils import context_utils
        context_utils.set_context_key_resolver(
            lambda state: state.get("session_id") or "default"
        )
    """
    global _context_key_resolver
    _context_key_resolver = resolver


def resolve_context_key(state: Mapping[str, Any]) -> str:
    """Resolve the context key from the given state.

    If a use-case resolver was set via set_context_key_resolver(), it is used.
    Otherwise uses state.get('context_key'); falls back to 'default' if missing
    or invalid.

    Args:
        state: Dict-like state (e.g. agent state with session_id, context_key).

    Returns:
        context_key string; 'default' if missing or invalid.
    """
    if _context_key_resolver is not None:
        return _context_key_resolver(state)
    context_key = state.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        logger.warning("Missing or invalid context_key in state; using 'default'")
        return "default"
    return context_key


def get_context(context_key: str) -> dict[str, Any]:
    """Load the current session context from the store.

    Args:
        context_key: Context key (session identifier).

    Returns:
        JSON-serializable context dict; empty dict if none exists.
    """
    store = get_context_store()
    context = store.get(context_key) or {}
    logger.info(
        "Loaded context for context_key '%s' with keys: %s", context_key, list(context.keys())
    )
    return context


def set_context(context_key: str, data: dict[str, Any]) -> str:
    """Replace the session context with the provided data.

    Args:
        context_key: Context key (session identifier).
        data: New context data.

    Returns:
        Success message.
    """
    store = get_context_store()
    store.set(context_key, data)
    logger.info("Set context for context_key '%s' with keys: %s", context_key, list(data.keys()))
    return "Context updated successfully."


def update_context(context_key: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial update to the session context.

    Args:
        context_key: Context key (session identifier).
        patch: Key-value updates to merge.

    Returns:
        The full context after the update.
    """
    store = get_context_store()
    updated = store.update(context_key, patch)
    logger.info(
        "Updated context for context_key '%s' with patch keys: %s; total keys now: %s",
        context_key,
        list(patch.keys()),
        list(updated.keys()),
    )
    return updated


def clear_context(context_key: str) -> str:
    """Clear any stored context for the session.

    Args:
        context_key: Context key (session identifier).

    Returns:
        Success message.
    """
    store = get_context_store()
    store.delete(context_key)
    logger.info("Cleared context for context_key '%s'", context_key)
    return "Context cleared successfully."


def resolve_workspace_context_for_file_api(
    workspace_context: str, state: Mapping[str, Any] | None
) -> str:
    """Resolve workspace_context for file API when empty or '{}'.

    Uses state.get('workspace_context') if present, otherwise loads from context
    store using context_key from state. Returns a JSON string suitable for file
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
    context_key = resolve_context_key(state)
    context = get_context(context_key)
    if not context:
        return "{}"
    if "workspace_context" in context:
        val = context["workspace_context"]
        if isinstance(val, dict):
            return json.dumps(val)
        if isinstance(val, str) and val.strip():
            return val
    return json.dumps(context)
