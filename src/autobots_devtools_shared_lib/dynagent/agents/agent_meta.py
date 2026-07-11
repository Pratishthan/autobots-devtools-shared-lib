# ABOUTME: Singleton holding all agent configuration loaded at startup.
# ABOUTME: Provides prompt_map, tool_map, input/output schema maps, and capabilities.

from __future__ import annotations

import json
from typing import Any

import autobots_devtools_shared_lib.dynagent.agents.agent_config_utils as _agent_config
from autobots_devtools_shared_lib.common.observability import get_logger

logger = get_logger(__file__)


class AgentMeta:
    """Lazy singleton for agent configuration."""

    _instance: AgentMeta | None = None
    prompt_map: dict[str, str]
    tool_map: dict[str, list[Any]]
    input_schema_map: dict[str, dict[str, dict]]
    output_schema_map: dict[str, dict | None]
    capabilities_map: dict[str, list[str]]
    default_agent: str | None
    model_map: dict[str, str | None]
    skills_map: dict[str, list[str]]
    memory_map: dict[str, list[str]]
    interrupt_map: dict[str, dict[str, Any]]
    permissions_map: dict[str, list[Any]]
    description_map: dict[str, str | None]
    mcp_map: dict[str, list[str]]
    debug_map: dict[str, bool]
    rubric_map: dict[str, dict[str, Any] | None]
    backend_config: dict[str, Any] | None
    model_profiles: dict[str, dict[str, Any]]
    mcp_servers_config: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self.prompt_map = _agent_config.get_prompt_map()
        self.tool_map = _agent_config.get_tool_map()
        self.input_schema_map = _agent_config.get_resolved_input_schema_map()
        self.output_schema_map = _agent_config.get_resolved_output_schema_map()
        self.capabilities_map = _agent_config.get_capabilities_map()
        self.default_agent = _agent_config.get_default_agent()
        self.model_map = _agent_config.get_model_map()
        self.skills_map = _agent_config.get_skills_map()
        self.memory_map = _agent_config.get_memory_map()
        self.interrupt_map = _agent_config.get_interrupt_map()
        self.permissions_map = _agent_config.get_permissions_map()
        self.description_map = _agent_config.get_description_map()
        self.mcp_map = _agent_config.get_mcp_map()
        self.debug_map = _agent_config.get_debug_map()
        self.rubric_map = _agent_config.get_rubric_map()
        self.backend_config = _agent_config.get_default_backend_config()
        self.model_profiles = _agent_config.get_model_profiles()
        self.mcp_servers_config = _agent_config.get_mcp_servers_config()
        logger.debug("%s", self)

    def __repr__(self) -> str:
        lines: list[str] = [f"AgentMeta(default_agent={self.default_agent!r})"]

        lines.append("\n=== prompt_map ===")
        lines.extend(f"  - {name}" for name in self.prompt_map)

        lines.append("\n=== tool_map ===")
        for name, tools in self.tool_map.items():
            tool_names = [getattr(t, "name", repr(t)) for t in tools]
            lines.append(f"  {name}: {tool_names}")

        lines.append("\n=== input_schema_map ===")
        lines.append(json.dumps(self.input_schema_map, indent=2, default=str))

        lines.append("\n=== output_schema_map ===")
        for name, schema in self.output_schema_map.items():
            lines.append(f"\n--- {name} ---")
            lines.append(json.dumps(schema, indent=2, default=str) if schema else "  (no schema)")

        lines.append("\n=== capabilities_map ===")
        lines.append(json.dumps(self.capabilities_map, indent=2))

        return "\n".join(lines)

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
