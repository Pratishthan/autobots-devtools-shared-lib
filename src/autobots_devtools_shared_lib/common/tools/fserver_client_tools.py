"""MCP tools wrapping File Server REST API endpoints."""

from langchain.tools import tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.fserver_client_utils import (
    create_download_link,
    get_disk_usage,
    list_files,
    move_file,
    read_file,
    write_file,
)

logger = get_logger(__name__)


@tool
def list_files_tool(base_path: str = "", workspace_context: str = "{}") -> str:
    """List all files in the specified directory or workspace."""
    return list_files(base_path, workspace_context)


@tool
def get_disk_usage_tool() -> str:
    """
    Get disk usage statistics for the file server.
    """
    return get_disk_usage()


@tool
def read_file_tool(file_name: str, workspace_context: str = "{}") -> str:
    """Read the content of a file."""
    return read_file(file_name, workspace_context)


@tool
def move_file_tool(source_path: str, destination_path: str, workspace_context: str = "{}") -> str:
    """Move a file from source to destination."""
    return move_file(source_path, destination_path, workspace_context)


@tool
def create_download_link_tool(file_name: str, workspace_context: str = "{}") -> str:
    """Create a download link for the file."""
    return create_download_link(file_name, workspace_context)


@tool
def write_file_tool(file_name: str, content: str, workspace_context: str = "{}") -> str:
    """Write content to a file."""
    return write_file(file_name, content, workspace_context)
