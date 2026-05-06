"""LangChain tools wrapping Node-RED instance manager REST API endpoints."""

from langchain.tools import ToolException, ToolRuntime, tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.noderedmanager_client_utils import (
    create_instance,
    get_health,
    kill_instance,
    list_instances,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

logger = get_logger(__name__)


def _session_id_from_runtime(runtime: ToolRuntime[None, Dynagent] | None) -> str | None:
    """Extract session_id from runtime state if available."""
    if runtime is None:
        return None
    state = runtime.state
    if state is None:
        return None
    session_id = state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    return session_id


def _check_result(result: str, operation: str) -> None:
    """If result is an error message, log and raise ToolException."""
    if result.strip().startswith("Error "):
        logger.warning("[tools] %s failed: %s", operation, result)
        raise ToolException(result)


@tool
def get_health_tool(runtime: ToolRuntime[None, Dynagent] | None = None) -> str:
    """Get the health status of the Node-RED instance manager server."""
    logger.info("[tools] Getting Node-RED manager health")
    try:
        result = get_health(session_id=_session_id_from_runtime(runtime))
        _check_result(result, "get_health")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] get_health_tool failed")
        raise ToolException(f"Error getting health: {e!s}") from e
    else:
        return result


@tool
def list_instances_tool(runtime: ToolRuntime[None, Dynagent] | None = None) -> str:
    """List all currently running Node-RED instances."""
    logger.info("[tools] Listing Node-RED instances")
    try:
        result = list_instances(session_id=_session_id_from_runtime(runtime))
        _check_result(result, "list_instances")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] list_instances_tool failed")
        raise ToolException(f"Error listing instances: {e!s}") from e
    else:
        return result


@tool
def create_instance_tool(
    runtime: ToolRuntime[None, Dynagent],
    workspace_base_path: str = "",
    flows_json_path: str = "",
    environment_name: str = "",
) -> str:
    """
    Launch a new Node-RED instance for the given workspace.

    Returns the instance id and URL. If an instance already exists for this workspace,
    the existing one is returned without launching a new process.
    """
    logger.info(
        "[tools] Creating Node-RED instance workspace=%r flows=%r environment=%r",
        workspace_base_path,
        flows_json_path,
        environment_name,
    )
    try:
        result = create_instance(
            workspace_base_path,
            flows_json_path,
            environment_name,
            session_id=_session_id_from_runtime(runtime),
        )
        _check_result(result, "create_instance")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] create_instance_tool failed workspace=%r", workspace_base_path)
        raise ToolException(f"Error creating instance: {e!s}") from e
    else:
        return result


@tool
def kill_instance_tool(
    runtime: ToolRuntime[None, Dynagent],
    workspace_base_path: str = "",
    environment_name: str = "",
) -> str:
    """Kill the running Node-RED instance for the given workspace and environment."""
    logger.info(
        "[tools] Killing Node-RED instance workspace=%r environment=%r",
        workspace_base_path,
        environment_name,
    )
    try:
        result = kill_instance(
            workspace_base_path,
            environment_name,
            session_id=_session_id_from_runtime(runtime),
        )
        _check_result(result, "kill_instance")
    except ToolException:
        raise
    except Exception as e:
        logger.exception(
            "[tools] kill_instance_tool failed workspace=%r environment=%r",
            workspace_base_path,
            environment_name,
        )
        raise ToolException(f"Error killing instance: {e!s}") from e
    else:
        return result
