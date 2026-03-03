# ABOUTME: Central registry of all dynagent-layer tools plus usecase-registered pools.
# ABOUTME: Default tools live here; use-cases (e.g. BRO) register their own at startup.

import threading
from typing import Any

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.tools.context_tools import make_context_tools
from autobots_devtools_shared_lib.common.tools.format_tools import output_format_converter_tool
from autobots_devtools_shared_lib.common.tools.fserver_client_tools import (
    create_download_link_tool,
    get_disk_usage_tool,
    list_files_tool,
    move_file_tool,
    read_file_tool,
    write_file_tool,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent
from autobots_devtools_shared_lib.dynagent.tools.state_tools import get_agent_list, handoff

logger = get_logger(__name__)

# --- Module-level usecase storage (populated by register_* at startup) ---

_USECASE_TOOLS: list[Any] = []

# --- Jenkins pipeline tool cache (None = not yet loaded) ---
# Loaded once on first get_jenkins_usecase_tools() call.
# [] means jenkins.yaml absent/unreadable — permanently cached, never retried.
# Double-checked locking guards against concurrent initialisation during I/O
# (CPython releases the GIL on file reads, making the race real).

_jenkins_tools_cache: list[Any] | None = None
_jenkins_tools_lock = threading.Lock()


# --- Default (dynagent-layer) tools ---


def get_default_tools() -> list[Any]:
    """Return the built-in dynagent-layer tools."""
    return [
        handoff,
        get_agent_list,
        output_format_converter_tool,
        *make_context_tools(Dynagent),
        get_disk_usage_tool,
        read_file_tool,
        move_file_tool,
        write_file_tool,
        list_files_tool,
        create_download_link_tool,
    ]


def get_jenkins_usecase_tools() -> list[Any]:
    """Return Jenkins pipeline tools discovered from jenkins.yaml.

    Thread-safe via double-checked locking:
    - Outer check avoids lock acquisition on every call once initialised (fast path).
    - Inner check inside the lock prevents duplicate initialisation when two threads
      race through the outer check simultaneously during I/O (GIL released on reads).
    Returns [] permanently if jenkins.yaml is absent or unreadable.
    """
    logger.info("Getting Jenkins pipeline tools")
    global _jenkins_tools_cache
    if _jenkins_tools_cache is None:  # 1st check — no lock (fast path)
        with _jenkins_tools_lock:  # acquire lock
            if _jenkins_tools_cache is None:  # 2nd check — inside lock (safe)
                from autobots_devtools_shared_lib.common.tools.jenkins_pipeline_tools import (
                    register_pipeline_tools,
                )

                _jenkins_tools_cache = register_pipeline_tools()
    return _jenkins_tools_cache


# --- Usecase registration (called once per use-case at startup) ---


def register_usecase_tools(tools: list[Any]) -> None:
    """Append use-case tools to the shared pool."""
    _USECASE_TOOLS.extend(tools)


# --- Read-only accessors ---


def get_usecase_tools() -> list[Any]:
    """Return a copy of the current usecase tool pool."""
    return list(_USECASE_TOOLS)


def get_all_tools() -> list[Any]:
    """Return default + usecase tools; usecase tools override defaults by name."""
    seen: dict[str, Any] = {}
    for t in get_default_tools():
        seen[t.name] = t
    for t in get_jenkins_usecase_tools():
        seen[t.name] = t
    for t in get_usecase_tools():
        seen[t.name] = t  # usecase wins on collision
    return list(seen.values())


# --- Test-isolation helpers (private; used only by fixtures) ---


def _reset_usecase_tools() -> None:
    global _jenkins_tools_cache
    _USECASE_TOOLS.clear()
    _jenkins_tools_cache = None
