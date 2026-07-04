# ABOUTME: Configuration utility functions for loading agent definitions.
# ABOUTME: Reads agents.yaml and provides typed accessors for prompts, tools, schemas.

import json
import os
import re
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
    "get_debug_map",
    "get_default_agent",
    "get_default_backend_config",
    "get_description_map",
    "get_interrupt_map",
    "get_mcp_map",
    "get_mcp_servers_config",
    "get_memory_map",
    "get_model_map",
    "get_model_profiles",
    "get_permissions_map",
    "get_prompt_map",
    "get_resolved_input_schema_map",
    "get_resolved_output_schema_map",
    "get_rubric_map",
    "get_skills_map",
    "get_tool_map",
    "interpolate_env",
    "load_agents_config",
    "load_prompt",
    "load_schema",
]

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def interpolate_env(value: Any) -> Any:
    """Recursively expand ${VAR} from os.environ in config values.

    Fails fast on undefined variables so misconfigured domains surface at
    startup instead of at first tool call.
    """
    if isinstance(value, str):

        def _sub(match: re.Match[str]) -> str:
            var = match.group(1)
            if var not in os.environ:
                msg = f"Config references undefined environment variable '${{{var}}}'"
                raise ValueError(msg)
            return os.environ[var]

        return _ENV_VAR_PATTERN.sub(_sub, value)
    if isinstance(value, dict):
        return {key: interpolate_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [interpolate_env(item) for item in value]
    return value


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
    # --- deep-engine-only fields (ignored by the react engine) ---
    model: str | None = None
    skills: list[str] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)
    interrupt_on: dict[str, Any] = field(default_factory=dict)
    permissions: list[Any] = field(default_factory=list)
    description: str | None = None
    mcp_servers: list[str] = field(default_factory=list)
    rubric: dict[str, Any] | None = None
    debug: bool = False

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
            model=data.get("model"),
            skills=list(data.get("skills") or []),
            memory=list(data.get("memory") or []),
            interrupt_on=dict(data.get("interrupt_on") or {}),
            permissions=list(data.get("permissions") or []),
            description=data.get("description"),
            mcp_servers=list(data.get("mcp_servers") or []),
            rubric=data.get("rubric"),
            debug=bool(data.get("debug", False)),
        )


_GLOBAL_AGENT_CONFIG: dict[str, AgentConfig] = {}
_GLOBAL_MODEL_PROFILES: dict[str, dict[str, Any]] = {}
_GLOBAL_BACKEND_CONFIG: dict[str, Any] | None = None
_GLOBAL_MCP_SERVERS: dict[str, dict[str, Any]] = {}


def _reset_agent_config() -> None:
    """Clear the cached agent config — for test isolation."""
    global _GLOBAL_AGENT_CONFIG, _GLOBAL_MODEL_PROFILES, _GLOBAL_BACKEND_CONFIG, _GLOBAL_MCP_SERVERS
    _GLOBAL_AGENT_CONFIG = {}
    _GLOBAL_MODEL_PROFILES = {}
    _GLOBAL_BACKEND_CONFIG = None
    _GLOBAL_MCP_SERVERS = {}


def get_config_dir() -> Path:
    """Get the configuration directory from dynagent settings (env: DYNAGENT_CONFIG_ROOT_DIR)."""
    config_dir = get_dynagent_settings().dynagent_config_root_dir
    logger.info(f"Using config directory: {config_dir}")
    return config_dir


# NOTE: Call get_config_dir() instead of using a global CONFIG_DIR to allow
# environment variable setup (e.g. in tests) before the path is resolved.


def load_agents_config() -> dict[str, AgentConfig]:
    """Load agent configurations from agents.yaml."""
    global _GLOBAL_AGENT_CONFIG, _GLOBAL_MODEL_PROFILES, _GLOBAL_BACKEND_CONFIG, _GLOBAL_MCP_SERVERS
    if _GLOBAL_AGENT_CONFIG:
        return _GLOBAL_AGENT_CONFIG
    config_dir = get_config_dir()
    config_path = Path(config_dir) / get_dynagent_settings().agents_config_filename

    with open(config_path) as f:  # noqa: PTH123
        data = yaml.safe_load(f)
    data = interpolate_env(data or {})

    _GLOBAL_MODEL_PROFILES = data.get("models") or {}
    _GLOBAL_BACKEND_CONFIG = data.get("default_backend")
    _GLOBAL_MCP_SERVERS = data.get("mcp_servers") or {}

    agents = {}
    for agent_id, agent_data in data.get("agents", {}).items():
        agents[agent_id] = AgentConfig.from_dict(agent_id, agent_data)

    from autobots_devtools_shared_lib.dynagent.llm.model_resolution import (
        validate_model_profiles,
        validate_model_ref,
    )

    validate_model_profiles(_GLOBAL_MODEL_PROFILES)
    for agent_id, agent_cfg in agents.items():
        if agent_cfg.model is not None:
            try:
                validate_model_ref(agent_cfg.model, _GLOBAL_MODEL_PROFILES)
            except ValueError as e:
                msg = f"Agent '{agent_id}': {e}"
                raise ValueError(msg) from e

    for agent_id, agent_cfg in agents.items():
        for server_name in agent_cfg.mcp_servers:
            if server_name not in _GLOBAL_MCP_SERVERS:
                msg = (
                    f"Agent '{agent_id}' references undeclared MCP server '{server_name}'. "
                    f"Declared servers: {sorted(_GLOBAL_MCP_SERVERS)}"
                )
                raise ValueError(msg)

    if get_dynagent_settings().agents_config_filename == "deep-agents.yaml":
        default_name = next((n for n, c in agents.items() if c.is_default), None)
        for agent_id, agent_cfg in agents.items():
            if agent_id != default_name and not agent_cfg.description:
                msg = (
                    f"Agent '{agent_id}': non-default deep-agent roster entries require a "
                    "description: (deepagents' task tool uses it for delegation)"
                )
                raise ValueError(msg)

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


def get_model_map() -> dict[str, str | None]:
    """Return {agent_name: model ref (profile / inline / bare) or None}."""
    return {name: c.model for name, c in load_agents_config().items()}


def get_skills_map() -> dict[str, list[str]]:
    """Return {agent_name: skill source paths}."""
    return {name: c.skills for name, c in load_agents_config().items()}


def get_memory_map() -> dict[str, list[str]]:
    """Return {agent_name: memory (AGENTS.md) paths}."""
    return {name: c.memory for name, c in load_agents_config().items()}


def get_interrupt_map() -> dict[str, dict[str, Any]]:
    """Return {agent_name: interrupt_on config}."""
    return {name: c.interrupt_on for name, c in load_agents_config().items()}


def get_permissions_map() -> dict[str, list[Any]]:
    """Return {agent_name: filesystem permission rules}."""
    return {name: c.permissions for name, c in load_agents_config().items()}


def get_description_map() -> dict[str, str | None]:
    """Return {agent_name: subagent description or None}."""
    return {name: c.description for name, c in load_agents_config().items()}


def get_mcp_map() -> dict[str, list[str]]:
    """Return {agent_name: referenced MCP server names}."""
    return {name: c.mcp_servers for name, c in load_agents_config().items()}


def get_debug_map() -> dict[str, bool]:
    """Return {agent_name: debug flag}."""
    return {name: c.debug for name, c in load_agents_config().items()}


def get_rubric_map() -> dict[str, dict[str, Any] | None]:
    """Return {agent_name: raw rubric config or None}."""
    return {name: c.rubric for name, c in load_agents_config().items()}


def get_model_profiles() -> dict[str, dict[str, Any]]:
    """Return the top-level models: block ({profile_name: {provider, name, temperature}})."""
    load_agents_config()
    return _GLOBAL_MODEL_PROFILES


def get_default_backend_config() -> dict[str, Any] | None:
    """Return the top-level default_backend: block, or None if not configured."""
    load_agents_config()
    return _GLOBAL_BACKEND_CONFIG


def get_mcp_servers_config() -> dict[str, dict[str, Any]]:
    """Return the top-level mcp_servers: block ({server_name: connection config})."""
    load_agents_config()
    return _GLOBAL_MCP_SERVERS
