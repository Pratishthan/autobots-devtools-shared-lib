# ABOUTME: Central registry of all dynagent-layer tools plus usecase-registered pools.
# ABOUTME: Default tools live here; use-cases (e.g. BRO) register their own at startup.

from typing import Any

from dynagent.tools.format_tools import convert_format
from dynagent.tools.state_tools import get_agent_list, handoff, read_file, write_file

# --- Module-level usecase storage (populated by register_* at startup) ---

_USECASE_TOOLS: list[Any] = []
_USECASE_OUTPUT_MODELS: dict[str, Any] = {}


# --- Default (dynagent-layer) tools ---


def get_default_tools() -> list[Any]:
    """Return the 5 built-in dynagent-layer tools."""
    return [handoff, get_agent_list, write_file, read_file, convert_format]


# --- Usecase registration (called once per use-case at startup) ---


def register_usecase_tools(tools: list[Any]) -> None:
    """Append use-case tools to the shared pool."""
    _USECASE_TOOLS.extend(tools)


def register_usecase_output_models(model_map: dict[str, Any]) -> None:
    """Merge use-case output-model map into the shared registry."""
    _USECASE_OUTPUT_MODELS.update(model_map)


# --- Read-only accessors ---


def get_usecase_tools() -> list[Any]:
    """Return a copy of the current usecase tool pool."""
    return list(_USECASE_TOOLS)


def get_all_tools() -> list[Any]:
    """Return default + usecase tools (the full pool passed to the agent)."""
    return get_default_tools() + get_usecase_tools()


def get_usecase_output_models() -> dict[str, Any]:
    """Return the merged usecase output-model map."""
    return dict(_USECASE_OUTPUT_MODELS)


# --- Test-isolation helpers (private; used only by fixtures) ---


def _reset_usecase_tools() -> None:
    _USECASE_TOOLS.clear()


def _reset_usecase_output_models() -> None:
    _USECASE_OUTPUT_MODELS.clear()
