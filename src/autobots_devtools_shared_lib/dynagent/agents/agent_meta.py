# ABOUTME: Singleton holding all agent configuration loaded at startup.
# ABOUTME: Provides prompt_map, tool_map, and schema_path_map.

from __future__ import annotations

from typing import Any

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import (
    get_prompt_map,
    get_schema_path_map,
    get_tool_map,
)


class AgentMeta:
    """Lazy singleton for agent configuration."""

    _instance: AgentMeta | None = None

    def __init__(self):
        self.prompt_map: dict[str, str] = get_prompt_map()
        self.tool_map: dict[str, list[Any]] = get_tool_map()
        self.schema_path_map: dict[str, str | None] = get_schema_path_map()

    @classmethod
    def instance(cls) -> AgentMeta:
        """Return the singleton, creating it on first access."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton — used for test isolation."""
        cls._instance = None
