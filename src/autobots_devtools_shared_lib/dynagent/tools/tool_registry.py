# ABOUTME: Central registry of all dynagent-layer tools plus usecase-registered pools.
# ABOUTME: Default tools live here; use-cases (e.g. BRO) register their own at startup.

from typing import Any

from autobots_devtools_shared_lib.dynagent.tools.format_tools import output_format_converter
from autobots_devtools_shared_lib.dynagent.tools.state_tools import get_agent_list, handoff, read_file, write_file

# --- Module-level usecase storage (populated by register_* at startup) ---

_USECASE_TOOLS: list[Any] = []


# --- Default (dynagent-layer) tools ---


def get_default_tools() -> list[Any]:
    """Return the 5 built-in dynagent-layer tools."""
    return [handoff, get_agent_list, write_file, read_file, output_format_converter]


# --- Usecase registration (called once per use-case at startup) ---


def register_usecase_tools(tools: list[Any]) -> None:
    """Append use-case tools to the shared pool."""
    _USECASE_TOOLS.extend(tools)


# --- Read-only accessors ---


def get_usecase_tools() -> list[Any]:
    """Return a copy of the current usecase tool pool."""
    return list(_USECASE_TOOLS)


def get_all_tools() -> list[Any]:
    """Return default + usecase tools (the full pool passed to the agent)."""
    return get_default_tools() + get_usecase_tools()


# --- Test-isolation helpers (private; used only by fixtures) ---


def _reset_usecase_tools() -> None:
    _USECASE_TOOLS.clear()
