"""MCP tools wrapping File Server REST API endpoints."""

from collections.abc import Mapping
from typing import Any

from langchain.tools import ToolException, ToolRuntime, tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.context_utils import (
    resolve_workspace_context_for_file_api,
)
from autobots_devtools_shared_lib.common.utils.fserver_client_utils import (
    create_download_link,
    get_disk_usage,
    list_files,
    move_file,
    read_file,
    write_file,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

logger = get_logger(__name__)


def _state_from_runtime(
    runtime: ToolRuntime[None, Dynagent] | None,
) -> Mapping[str, Any] | None:
    """Return state from runtime if available."""
    return runtime.state if runtime is not None else None


def _session_id_from_runtime(runtime: ToolRuntime[None, Dynagent] | None) -> str | None:
    """Extract session_id from runtime state if available."""
    if runtime is None:
        return None
    state = runtime.state
    if state is None:
        return None
    session_id = state.get("session_id")
    # Validate it's a non-empty string
    if not isinstance(session_id, str) or not session_id:
        return None
    return session_id


def _check_result(result: str, operation: str) -> None:
    """If result is an error message, log and raise ToolException."""
    if result.strip().startswith("Error "):
        logger.warning("[tools] %s failed: %s", operation, result)
        raise ToolException(result)


@tool
def list_files_tool(
    runtime: ToolRuntime[None, Dynagent],
    base_path: str = "",
    workspace_context: str = "{}",
) -> str:
    """List all files in the specified directory or workspace."""
    logger.info("[tools] Listing files base_path=%r", base_path)
    try:
        workspace_context = resolve_workspace_context_for_file_api(
            workspace_context, _state_from_runtime(runtime)
        )
        logger.info("[tools] formed workspace_context=%s", workspace_context)
        result = list_files(
            base_path, workspace_context, session_id=_session_id_from_runtime(runtime)
        )
        _check_result(result, "list_files")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] list_files_tool failed")
        raise ToolException(f"Error listing files: {e!s}") from e
    else:
        return result


@tool
def get_disk_usage_tool(runtime: ToolRuntime[None, Dynagent] | None = None) -> str:
    """
    Get disk usage statistics for the file server.
    """
    logger.info("[tools] Getting disk usage")
    try:
        result = get_disk_usage(session_id=_session_id_from_runtime(runtime))
        _check_result(result, "get_disk_usage")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] get_disk_usage_tool failed")
        raise ToolException(f"Error getting disk usage: {e!s}") from e
    else:
        return result


@tool
def read_file_tool(
    runtime: ToolRuntime[None, Dynagent],
    file_name: str = "",
    workspace_context: str = "{}",
) -> str:
    """Read the content of a file."""
    logger.info("[tools] Reading file file_name=%r", file_name)
    try:
        workspace_context = resolve_workspace_context_for_file_api(
            workspace_context, _state_from_runtime(runtime)
        )
        logger.info("[tools] formed workspace_context=%s", workspace_context)
        result = read_file(
            file_name, workspace_context, session_id=_session_id_from_runtime(runtime)
        )
        _check_result(result, "read_file")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] read_file_tool failed for file_name=%r", file_name)
        raise ToolException(f"Error reading file: {e!s}") from e
    else:
        return result


@tool
def move_file_tool(
    runtime: ToolRuntime[None, Dynagent],
    source_path: str = "",
    destination_path: str = "",
    workspace_context: str = "{}",
) -> str:
    """Move a file from source to destination."""
    logger.info(
        "[tools] Moving file source_path=%r destination_path=%r",
        source_path,
        destination_path,
    )
    try:
        workspace_context = resolve_workspace_context_for_file_api(
            workspace_context, _state_from_runtime(runtime)
        )
        logger.info("[tools] formed workspace_context=%s", workspace_context)
        result = move_file(
            source_path,
            destination_path,
            workspace_context,
            session_id=_session_id_from_runtime(runtime),
        )
        _check_result(result, "move_file")
    except ToolException:
        raise
    except Exception as e:
        logger.exception(
            "[tools] move_file_tool failed source_path=%r destination_path=%r",
            source_path,
            destination_path,
        )
        raise ToolException(f"Error moving file: {e!s}") from e
    else:
        return result


@tool
def create_download_link_tool(
    runtime: ToolRuntime[None, Dynagent],
    file_name: str = "",
    workspace_context: str = "{}",
) -> str:
    """Create a download link for the file."""
    logger.info("[tools] Creating download link file_name=%r", file_name)
    try:
        workspace_context = resolve_workspace_context_for_file_api(
            workspace_context, _state_from_runtime(runtime)
        )
        logger.info("[tools] formed workspace_context=%s", workspace_context)
        result = create_download_link(
            file_name, workspace_context, session_id=_session_id_from_runtime(runtime)
        )
        _check_result(result, "create_download_link")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] create_download_link_tool failed for file_name=%r", file_name)
        raise ToolException(f"Error creating download link: {e!s}") from e
    else:
        return result


@tool
def write_file_tool(
    runtime: ToolRuntime[None, Dynagent],
    file_name: str = "",
    content: str = "",
    workspace_context: str = "{}",
) -> str:
    """Write content to a file."""
    logger.info("[tools] Writing file file_name=%r content_len=%s", file_name, len(content))
    try:
        workspace_context = resolve_workspace_context_for_file_api(
            workspace_context, _state_from_runtime(runtime)
        )
        logger.info("[tools] formed workspace_context=%s", workspace_context)
        result = write_file(
            file_name, content, workspace_context, session_id=_session_id_from_runtime(runtime)
        )
        _check_result(result, "write_file")
    except ToolException:
        raise
    except Exception as e:
        logger.exception("[tools] write_file_tool failed for file_name=%r", file_name)
        raise ToolException(f"Error writing file: {e!s}") from e
    else:
        return result
