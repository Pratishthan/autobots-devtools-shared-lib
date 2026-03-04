# ABOUTME: Thin LangChain agent layer — wraps JenkinsPipelineRunner as StructuredTools.
# ABOUTME: All execution logic lives in common/utils/jenkins_pipeline_utils.py.
# ABOUTME: register_pipeline_tools() is the single entry point for agent tool registration.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from autobots_devtools_shared_lib.common.config.jenkins_constants import (
    ARGS_SCHEMA_SUFFIX,
    TOOL_NAME_SUFFIX,
)
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.tools.jenkins_builtin_tools import (
    get_jenkins_build_status,
    get_jenkins_console_log,
)
from autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils import get_pipeline_runner

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.common.config.jenkins_config import JenkinsPipelineConfig

logger = get_logger(__name__)

_PYTHON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "str": str,
    "boolean": bool,
    "bool": bool,
    "integer": int,
    "int": int,
    "float": float,
    "number": float,
}


def _build_args_schema(tool_name: str, pipeline_cfg: JenkinsPipelineConfig) -> type[BaseModel]:
    """Build a dynamic Pydantic model from a pipeline's parameters.

    Required parameters get a plain Field; optional ones get ``type | None`` with default None.
    """
    field_definitions: dict[str, Any] = {}
    for param_name, param_cfg in pipeline_cfg.parameters.items():
        py_type = _PYTHON_TYPE_MAP.get(param_cfg.type.lower(), str)
        if param_cfg.required:
            field_definitions[param_name] = (py_type, Field(description=param_cfg.description))
        else:
            field_definitions[param_name] = (
                py_type | None,
                Field(default=None, description=param_cfg.description),
            )
    return create_model(f"{tool_name}{ARGS_SCHEMA_SUFFIX}", **field_definitions)


def create_jenkins_tools() -> list[Any]:
    """Generate LangChain StructuredTools from the loaded JenkinsConfig.

    For each entry in ``config.pipelines`` a StructuredTool is created whose
    name is ``{pipeline_key}_tool`` (e.g. pipeline key ``create_workspace``
    → tool name ``create_workspace_tool``).

    Config is loaded lazily via get_pipeline_runner() — no explicit config
    argument needed. Call register_pipeline_tools() as the higher-level entry
    point which also includes the builtin observability tools.

    Returns:
        List of pipeline StructuredTools ready for ``register_usecase_tools()``.
        The builtin observability tools are not included here.

    Raises:
        RuntimeError: If jenkins.yaml cannot be found.
    """
    runner = get_pipeline_runner()
    tools: list[Any] = []

    for pipeline_name, pipeline_cfg in runner._config.pipelines.items():
        tool_name = f"{pipeline_name}{TOOL_NAME_SUFFIX}"
        args_schema = _build_args_schema(tool_name, pipeline_cfg)
        description = pipeline_cfg.description or f"Trigger Jenkins pipeline: {pipeline_cfg.uri}"

        tools.append(
            StructuredTool.from_function(
                func=runner.get_callable(pipeline_name),
                name=tool_name,
                description=description,
                args_schema=args_schema,
            )
        )
        logger.info(f"Registered Jenkins tool '{tool_name}' → {pipeline_cfg.uri}")

    return tools


def register_pipeline_tools() -> list[Any]:
    """Load jenkins.yaml and return all Jenkins tools (pipeline + builtin observability).

    Returns an empty list when jenkins.yaml is absent — Jenkins integration is optional.
    Config loading and caching is handled internally; no setup required before calling.
    """
    try:
        from autobots_devtools_shared_lib.common.config.jenkins_loader import get_jenkins_config

        if get_jenkins_config() is not None:
            logger.info("Loading Jenkins pipeline tools")
            pipeline_tools = create_jenkins_tools()
            all_tools = [get_jenkins_build_status, get_jenkins_console_log, *pipeline_tools]
            logger.info(
                f"Loaded {len(pipeline_tools)} pipeline tool(s) + 2 builtin Jenkins tools"
                " from jenkins.yaml"
            )
            return all_tools
    except Exception:
        logger.exception("Failed to load Jenkins pipeline tools — continuing without them")
    return []
