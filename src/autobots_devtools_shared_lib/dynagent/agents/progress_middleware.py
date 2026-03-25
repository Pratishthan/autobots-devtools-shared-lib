# ABOUTME: ProgressPersistenceMiddleware — mirrors agent todos to workspace_progress.
# ABOUTME: Uses a module-level callback so shared-lib stays decoupled from MER's DB.

from __future__ import annotations

from typing import TYPE_CHECKING

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

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
