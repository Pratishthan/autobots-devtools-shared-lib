"""MCP tools wrapping File Server REST API endpoints."""

import base64
import json
import os

import httpx

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

# Set up logging
logger = get_logger(__name__)
# File server configuration (set FILE_SERVER_HOST for your environment, e.g. in .env)
FILE_SERVER_HOST = os.getenv("FILE_SERVER_HOST", "localhost")
FILE_SERVER_PORT = os.getenv("FILE_SERVER_PORT", "9002")
FILE_SERVER_BASE_URL = f"http://{FILE_SERVER_HOST}:{FILE_SERVER_PORT}"


def _parse_workspace_context(workspace_context: str) -> dict:
    """Parse optional JSON workspace context for API payloads. Returns dict (empty if invalid)."""
    if not workspace_context or not workspace_context.strip():
        return {}
    try:
        out = json.loads(workspace_context)
        return out if isinstance(out, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def list_files(base_path: str = "", workspace_context: str = "{}") -> str:
    """
    List all files in the specified directory or workspace.

    Args:
        base_path: Optional subdirectory to list from.
        workspace_context: Optional JSON object for workspace/scoping (e.g. {"agent_name": "...", "user_name": "...", "repo_name": "...", "jira_number": "..."}). Merged into the API request as-is.

    Returns:
        JSON string of file paths
    """
    logger.info(
        "Listing files with base_path='%s', workspace_context=%s", base_path, workspace_context
    )
    try:
        payload = {
            "path": base_path if base_path else None,
            **_parse_workspace_context(workspace_context),
        }

        with httpx.Client() as client:
            response = client.post(f"{FILE_SERVER_BASE_URL}/listFiles", json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        files = result.get("files", [])
        logger.info(f"Successfully listed {len(files)} files")
        return str(files)
    except httpx.HTTPStatusError as e:
        logger.exception(f"HTTP error listing files: {e.response.status_code} - {e.response.text}")
        return f"Error listing files: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.exception("Error listing files")
        return f"Error listing files: {e!s}"


def get_disk_usage() -> str:
    """
    Get disk usage statistics for the file server.

    Returns:
        JSON string with disk usage information
    """
    logger.info("Getting disk usage statistics")
    try:
        with httpx.Client() as client:
            response = client.get(f"{FILE_SERVER_BASE_URL}/health", timeout=30.0)
            response.raise_for_status()
            result = response.json()

        disk_usage = result.get("disk_usage", {})
        logger.info("Successfully retrieved disk usage information")
        return str(disk_usage)
    except httpx.HTTPStatusError as e:
        logger.exception(
            f"HTTP error getting disk usage: {e.response.status_code} - {e.response.text}"
        )
        return f"Error getting disk usage: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.exception("Error getting disk usage")
        return f"Error getting disk usage: {e!s}"


def read_file(file_name: str, workspace_context: str = "{}") -> str:
    """
    Read the content of a file.

    Args:
        file_name: Relative file path.
        workspace_context: Optional JSON object for workspace/scoping (e.g. {"agent_name": "...", "user_name": "...", "repo_name": "...", "jira_number": "..."}). Merged into the API request as-is.

    Returns:
        File content as string (UTF-8 for text files, base64 for binary files)
    """
    logger.info("Reading file '%s' with workspace_context=%s", file_name, workspace_context)
    try:
        payload = {"fileName": file_name, **_parse_workspace_context(workspace_context)}

        with httpx.Client() as client:
            response = client.post(f"{FILE_SERVER_BASE_URL}/readFile", json=payload, timeout=30.0)
            response.raise_for_status()
            content = response.content

        logger.info(f"Successfully read file '{file_name}' ({len(content)} bytes)")

        # Try to decode as UTF-8 for text files
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            # For binary files (e.g., .xlsx, .pdf, .zip), return base64-encoded content
            logger.info(f"File '{file_name}' is binary, returning as base64")
            return base64.b64encode(content).decode("utf-8")

    except httpx.HTTPStatusError as e:
        logger.exception(
            f"HTTP error reading file '{file_name}': {e.response.status_code} - {e.response.text}"
        )
        return f"Error reading file: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.exception("Error reading file '%s'", file_name)
        return f"Error reading file: {e!s}"


def write_file(file_name: str, content: str, workspace_context: str = "{}") -> str:
    """
    Write content to a file.

    Args:
        file_name: Relative file path.
        content: File content as string.
        workspace_context: Optional JSON object for workspace/scoping (e.g. {"agent_name": "...", "user_name": "...", "repo_name": "...", "jira_number": "..."}). Merged into the API request as-is.

    Returns:
        Success message with file path and size
    """
    logger.info("Writing to file '%s' with workspace_context=%s", file_name, workspace_context)
    try:
        content_base64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {
            "file_name": file_name,
            "file_content": content_base64,
            **_parse_workspace_context(workspace_context),
        }

        with httpx.Client() as client:
            response = client.post(f"{FILE_SERVER_BASE_URL}/writeFile", json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        logger.info(
            f"Successfully wrote file '{result['path']}' with size {result['size_bytes']} bytes"
        )
        return f"File written successfully: {result['path']}, size: {result['size_bytes']} bytes"
    except httpx.HTTPStatusError as e:
        logger.exception(
            f"HTTP error writing file '{file_name}': {e.response.status_code} - {e.response.text}"
        )
        return f"Error writing file: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.exception("Error writing file '%s'", file_name)
        return f"Error writing file: {e!s}"


def move_file(source_path: str, destination_path: str, workspace_context: str = "{}") -> str:
    """
    Move a file from source to destination.

    Args:
        source_path: Current file path.
        destination_path: New file path.
        workspace_context: Optional JSON object for workspace/scoping (e.g. {"agent_name": "...", "user_name": "...", "repo_name": "...", "jira_number": "..."}). Merged into the API request as-is.

    Returns:
        Success message with file paths and size
    """
    logger.info(
        "Moving file from '%s' to '%s' with workspace_context=%s",
        source_path,
        destination_path,
        workspace_context,
    )
    try:
        payload = {
            "source_path": source_path,
            "destination_path": destination_path,
            **_parse_workspace_context(workspace_context),
        }

        with httpx.Client() as client:
            response = client.post(f"{FILE_SERVER_BASE_URL}/moveFile", json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        logger.info(
            f"Successfully moved file from '{source_path}' to '{result['destination_path']}' ({result['size_bytes']} bytes)"
        )
        return f"File moved successfully: {result['message']}, size: {result['size_bytes']} bytes"
    except httpx.HTTPStatusError as e:
        logger.exception(
            f"HTTP error moving file from '{source_path}' to '{destination_path}': {e.response.status_code} - {e.response.text}"
        )
        return f"Error moving file: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.exception("Error moving file from '%s' to '%s'", source_path, destination_path)
        return f"Error moving file: {e!s}"


def create_download_link(file_name: str, workspace_context: str = "{}") -> str:
    """
    Create a download link for the file.

    Args:
        file_name: Relative file path.
        workspace_context: Optional JSON object for workspace/scoping (e.g. {"agent_name": "...", "user_name": "...", "repo_name": "...", "jira_number": "..."}). Merged into the API request as-is.

    Returns:
        Creates a download link for the file
    """
    logger.info(
        "Creating download link for '%s' with workspace_context=%s", file_name, workspace_context
    )
    try:
        payload = {"fileName": file_name, **_parse_workspace_context(workspace_context)}

        with httpx.Client() as client:
            response = client.post(
                f"{FILE_SERVER_BASE_URL}/createDownloadLink", json=payload, timeout=30.0
            )
            response.raise_for_status()
            content = response.content

        logger.info(f"Successfully read file '{file_name}' ({len(content)} bytes)")

        # Try to decode as UTF-8 for text files
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            # For binary files (e.g., .xlsx, .pdf, .zip), return base64-encoded content
            logger.info(f"File '{file_name}' is binary, returning as base64")
            return base64.b64encode(content).decode("utf-8")

    except httpx.HTTPStatusError as e:
        logger.exception(
            f"HTTP error reading file '{file_name}': {e.response.status_code} - {e.response.text}"
        )
        return f"Error reading file: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.exception("Error reading file '%s'", file_name)
        return f"Error reading file: {e!s}"


if __name__ == "__main__":
    logger.info("Testing File Server Client Tools")
