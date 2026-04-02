# ABOUTME: Singleton holding all agent configuration loaded at startup.
# ABOUTME: Provides prompt_map, tool_map, input/output schema maps, and capabilities.

from __future__ import annotations

from typing import Any

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as _agent_config


class AgentMeta:
    """Lazy singleton for agent configuration."""

    _instance: AgentMeta | None = None
    prompt_map: dict[str, str]
    tool_map: dict[str, list[Any]]
    input_schema_map: dict[str, dict[str, dict]]
    output_schema_map: dict[str, dict | None]
    capabilities_map: dict[str, list[str]]
    default_agent: str | None

    def __init__(self) -> None:
        self.prompt_map = _agent_config.get_prompt_map()
        self.tool_map = _agent_config.get_tool_map()
        self.input_schema_map = _agent_config.get_resolved_input_schema_map()
        self.output_schema_map = _agent_config.get_resolved_output_schema_map()
        self.capabilities_map = _agent_config.get_capabilities_map()
        self.default_agent = _agent_config.get_default_agent()

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
