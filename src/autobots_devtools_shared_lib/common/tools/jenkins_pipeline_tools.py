# ABOUTME: Generates LangChain StructuredTools from JenkinsConfig at startup.
# ABOUTME: One tool is created per pipeline entry; tool name = "{pipeline_key}_tool".
# ABOUTME: register_pipeline_tools() is the single entry point for auto-registration.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.tools.jenkins_builtin_tools import (
    get_jenkins_build_status,
    get_jenkins_console_log,
    set_jenkins_config,
)
from autobots_devtools_shared_lib.common.utils.jenkins_http_utils import (
    extract_job_name_from_url,
    get_auth,
    poll_queue_for_build_number,
    wait_for_build,
)

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.common.config.jenkins_config import (
        JenkinsConfig,
        JenkinsPipelineConfig,
    )

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
    return create_model(f"{tool_name}_args", **field_definitions)


def _make_trigger_fn(
    tool_name: str,
    pipeline_cfg: JenkinsPipelineConfig,
    config: JenkinsConfig,
) -> Any:
    """Return a closure that triggers the Jenkins pipeline and handles completion polling."""
    effective_polling = pipeline_cfg.polling or config.polling
    full_url = config.base_url.rstrip("/") + pipeline_cfg.uri

    def trigger(**kwargs: Any) -> str:
        auth = get_auth(config)
        query_params = {k: v for k, v in kwargs.items() if v is not None}
        logger.info(
            f"Triggering Jenkins tool '{tool_name}': POST {full_url} params={list(query_params)}"
        )
        try:
            response = requests.post(full_url, params=query_params, auth=auth, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.exception(f"Jenkins trigger failed for '{tool_name}'")
            return f"Error triggering Jenkins pipeline: {exc}"

        queue_location = response.headers.get("Location", "")
        build_info = poll_queue_for_build_number(queue_location, effective_polling, auth)

        if build_info["status"] != "success":
            return build_info["message"]

        build_number: int = build_info["build_number"]
        build_url: str = build_info["build_url"]

        if not effective_polling.wait_for_completion:
            logger.info(f"Fire-and-forget: build #{build_number} triggered at {build_url}")
            return f"Build #{build_number} triggered: {build_url}"

        job_name = extract_job_name_from_url(pipeline_cfg.uri)
        return wait_for_build(config.base_url, job_name, build_number, effective_polling, auth)

    trigger.__name__ = tool_name
    return trigger


def create_jenkins_tools(config: JenkinsConfig) -> list[Any]:
    """Generate LangChain StructuredTools from a JenkinsConfig.

    For each entry in ``config.pipelines`` a StructuredTool is created whose
    name is ``{pipeline_key}_tool`` (e.g. pipeline key ``create_workspace``
    → tool name ``create_workspace_tool``).

    Args:
        config: Validated JenkinsConfig loaded from jenkins.yaml.

    Returns:
        List of pipeline StructuredTools ready for ``register_usecase_tools()``.
        The builtin observability tools are default tools and not included here.
    """

    tools: list[Any] = []

    for pipeline_name, pipeline_cfg in config.pipelines.items():
        tool_name = f"{pipeline_name}_tool"
        args_schema = _build_args_schema(tool_name, pipeline_cfg)
        trigger_fn = _make_trigger_fn(tool_name, pipeline_cfg, config)
        description = pipeline_cfg.description or f"Trigger Jenkins pipeline: {pipeline_cfg.uri}"

        tools.append(
            StructuredTool.from_function(
                func=trigger_fn,
                name=tool_name,
                description=description,
                args_schema=args_schema,
            )
        )
        logger.info(f"Registered Jenkins tool '{tool_name}' → {pipeline_cfg.uri}")

    return tools


def register_pipeline_tools() -> list[Any]:
    """Load jenkins.yaml and return dynamic pipeline tools.

    Returns an empty list when jenkins.yaml is absent or unreadable.
    Callers are responsible for caching the result — this function always
    reads from disk on each invocation.
    """
    try:
        from autobots_devtools_shared_lib.common.config.jenkins_loader import load_jenkins_config

        logger.info("Loading Jenkins pipeline tools")
        config = load_jenkins_config()
        if config:
            set_jenkins_config(config)
            pipeline_tools = create_jenkins_tools(config)
            # Builtins require a valid config (set inside create_jenkins_tools via set_jenkins_config).
            # Include them here so they are only available when Jenkins is actually configured.
            all_tools = [get_jenkins_build_status, get_jenkins_console_log, *pipeline_tools]
            logger.info(
                f"Loaded {len(pipeline_tools)} pipeline tool(s) + 2 builtin Jenkins tools"
                " from jenkins.yaml"
            )
            return all_tools
    except Exception:
        logger.exception("Failed to load Jenkins pipeline tools — continuing without them")
    return []
