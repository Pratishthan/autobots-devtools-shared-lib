# ABOUTME: Configuration utility functions for loading agent definitions.
# ABOUTME: Reads agents.yaml and provides typed accessors for prompts, tools, schemas.

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import get_dynagent_settings
from autobots_devtools_shared_lib.dynagent.utils.schema_directive_resolver import (
    resolve_parent_with_directives,
)

logger = get_logger(__name__)

__all__ = [
    "AgentConfig",
    "get_agent_list",
    "get_batch_enabled_agents",
    "get_capabilities_map",
    "get_config_dir",
    "get_default_agent",
    "get_prompt_map",
    "get_resolved_input_schema_map",
    "get_resolved_output_schema_map",
    "get_tool_map",
    "load_agents_config",
    "load_prompt",
    "load_schema",
]


@dataclass
class AgentConfig:
    """Configuration for an agent loaded from agents.yaml."""

    agent_id: str
    prompt: str
    tools: list[str]
    # inputs: schema_name -> directive_filename (or None)
    inputs: dict[str, str | None] = field(default_factory=dict)
    # output: single-entry {schema_name -> directive_filename} map (or None)
    output: dict[str, str | None] | None = None
    # optional list of human-readable capabilities
    capabilities: list[str] = field(default_factory=list)
    section: str | None = None
    approach: str | None = None
    dynamic: bool = False
    batch_enabled: bool = False
    is_default: bool = False
    max_concurrency: int | None = None

    @classmethod
    def from_dict(cls, agent_id: str, data: dict[str, Any]) -> "AgentConfig":
        """Create AgentConfig from a dictionary."""

        raw_inputs = data.get("inputs") or []
        inputs: dict[str, str | None] = {}
        for item in raw_inputs:
            if not isinstance(item, dict):
                continue
            schema_name = item.get("schema")
            if not schema_name:
                continue
            directives_name = item.get("directives")
            inputs[schema_name] = directives_name

        raw_output = data.get("output")
        output_cfg: dict[str, str | None] | None = None
        if isinstance(raw_output, dict):
            schema_name_val = raw_output.get("schema")
            directives_name_val = raw_output.get("directives")
            if isinstance(schema_name_val, str) or isinstance(directives_name_val, str):
                schema_key = schema_name_val if isinstance(schema_name_val, str) else ""
                output_cfg = {
                    schema_key: directives_name_val
                    if isinstance(directives_name_val, str)
                    else None
                }

        raw_capabilities = data.get("capabilities")
        capabilities: list[str] = []
        if isinstance(raw_capabilities, list):
            capabilities = [item for item in raw_capabilities if isinstance(item, str)]

        return cls(
            agent_id=agent_id,
            prompt=data.get("prompt", ""),
            tools=data.get("tools", []),
            inputs=inputs,
            output=output_cfg,
            capabilities=capabilities,
            section=data.get("section"),
            approach=data.get("approach"),
            dynamic=data.get("dynamic", False),
            batch_enabled=data.get("batch_enabled", False),
            is_default=data.get("is_default", False),
            max_concurrency=data.get("max_concurrency"),
        )


_GLOBAL_AGENT_CONFIG: dict[str, AgentConfig] = {}


def _reset_agent_config() -> None:
    """Clear the cached agent config — for test isolation."""
    global _GLOBAL_AGENT_CONFIG
    _GLOBAL_AGENT_CONFIG = {}


def get_config_dir() -> Path:
    """Get the configuration directory from dynagent settings (env: DYNAGENT_CONFIG_ROOT_DIR)."""
    config_dir = get_dynagent_settings().dynagent_config_root_dir
    logger.info(f"Using config directory: {config_dir}")
    return config_dir


# NOTE: Call get_config_dir() instead of using a global CONFIG_DIR to allow
# environment variable setup (e.g. in tests) before the path is resolved.


def load_agents_config() -> dict[str, AgentConfig]:
    """Load agent configurations from agents.yaml."""
    global _GLOBAL_AGENT_CONFIG
    if _GLOBAL_AGENT_CONFIG:
        return _GLOBAL_AGENT_CONFIG
    config_dir = get_config_dir()
    config_path = Path(config_dir) / get_dynagent_settings().agents_config_filename

    with open(config_path) as f:  # noqa: PTH123
        data = yaml.safe_load(f)

    agents = {}
    for agent_id, agent_data in data.get("agents", {}).items():
        agents[agent_id] = AgentConfig.from_dict(agent_id, agent_data)

    _GLOBAL_AGENT_CONFIG = agents

    logger.info(f"Loaded {len(_GLOBAL_AGENT_CONFIG)} agent configs from {config_path}")
    return agents


def load_prompt(name: str) -> str:
    """Read a prompt file by name from the prompts/ directory."""
    config_dir = get_config_dir()
    prompt_dir = Path(config_dir) / "prompts"
    try:
        with open(prompt_dir / f"{name}.md") as f:  # noqa: PTH123
            return f.read()
    except Exception as e:
        logger.exception(f"Error reading prompt {name} from {prompt_dir}")
        return f"Error reading prompt: {e}"


def load_schema(name: str, base_dir: Path | None = None) -> dict:
    """Read and parse a JSON schema file by name.

    When base_dir is provided, reads from base_dir/schemas; otherwise uses
    the active config_dir/schemas.
    """
    if base_dir is None:
        base_dir = get_config_dir()
    schema_dir = Path(base_dir) / "schemas"
    schema_file = schema_dir / name

    if not schema_file.exists():
        error_msg = f"Schema file not found: {schema_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with Path.open(schema_file) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in schema {schema_file}: {e}"
        logger.exception(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Error reading schema {name} from {schema_dir}: {e}"
        logger.exception(error_msg)
        raise


def _build_parent_paths(schema_name: str) -> list[Path]:
    """Compute candidate parent schema paths in common and domain-specific folders."""
    config_dir = get_config_dir()
    if not schema_name.endswith(".json"):
        schema_name = f"{schema_name}.json"

    domain_schema = Path(config_dir) / "schemas" / schema_name
    common_schema = Path(config_dir).parent / "common" / "schemas" / schema_name
    return [common_schema, domain_schema]


def _normalize_directive_filename(directive_name: str) -> str:
    """Ensure directive filenames resolve to json files."""
    return directive_name if directive_name.endswith(".json") else f"{directive_name}.json"


def get_resolved_input_schema_map() -> dict[str, dict[str, dict]]:
    """Return {agent_name: {schema_key: resolved_schema_dict}} for all input schemas."""
    config_dir = get_config_dir()
    agents = load_agents_config()

    result: dict[str, dict[str, dict]] = {}

    for agent_name, cfg in agents.items():
        per_agent: dict[str, dict] = {}
        for schema_name, directive_name in cfg.inputs.items():
            if not directive_name:
                continue
            parent_paths = _build_parent_paths(schema_name)
            directive_path = (
                config_dir / "directives" / _normalize_directive_filename(directive_name)
            )
            resolved = resolve_parent_with_directives(parent_paths, directive_path)
            schema_key = Path(schema_name).stem
            per_agent[schema_key] = resolved
        result[agent_name] = per_agent

    return result


def _resolve_output_schema_for_agent(cfg: AgentConfig, config_dir: Path) -> dict | None:
    """Resolve a single agent's output schema from output schema+directive config."""
    if cfg.output is None:
        return None

    # Expect at most one entry in the output map.
    for schema_name, directive_name in cfg.output.items():
        if not schema_name:
            return None
        parent_paths = _build_parent_paths(schema_name)
        if directive_name:
            directive_path = (
                config_dir / "directives" / _normalize_directive_filename(directive_name)
            )
            return resolve_parent_with_directives(parent_paths, directive_path)

        return resolve_parent_with_directives(parent_paths, None)

    return None


def get_resolved_output_schema_map() -> dict[str, dict | None]:
    """Return {agent_name: resolved output schema or None} for all agents."""
    config_dir = get_config_dir()
    agents = load_agents_config()
    return {
        agent_name: _resolve_output_schema_for_agent(cfg, config_dir)
        for agent_name, cfg in agents.items()
    }


def get_agent_list() -> list[str]:
    """Return list of agent names from config."""
    return list(load_agents_config().keys())


def get_prompt_map() -> dict[str, str]:
    """Return {agent_name: prompt_text} loaded from prompt files."""
    return {name: load_prompt(cfg.prompt) for name, cfg in load_agents_config().items()}


def get_capabilities_map() -> dict[str, list[str]]:
    """Return {agent_name: capabilities[]} from agents config."""
    return {name: cfg.capabilities for name, cfg in load_agents_config().items()}


def get_tool_map() -> dict[str, list[Any]]:
    """Return {agent_name: [tool_objects]}.

    Resolves each agent's tool list from agents.yaml against the combined
    default + usecase tool pool.

    Raises:
        ValueError: If a tool name referenced in agents.yaml cannot be resolved
    """
    from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_all_tools

    all_tools = get_all_tools()
    tool_by_name = {t.name: t for t in all_tools}
    result: dict[str, list[Any]] = {}
    for name, cfg in load_agents_config().items():
        resolved: list[Any] = []
        for tool_name in cfg.tools:
            if tool_name in tool_by_name:
                resolved.append(tool_by_name[tool_name])
                logger.info(f"Agent '{name}': adding resolved tool '{tool_name}'")
            else:
                error_msg = f"Unresolved tool '{tool_name}' for agent '{name}'. Available tools: {sorted(tool_by_name.keys())}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        result[name] = resolved
    return result


def get_batch_enabled_agents() -> list[str]:
    """Return list of agent names that have batch_enabled=True."""
    return [name for name, cfg in load_agents_config().items() if cfg.batch_enabled]


def get_default_agent() -> str | None:
    """Return the name of the default agent, or None if not set."""
    for name, cfg in load_agents_config().items():
        if cfg.is_default:
            return name
    return None
