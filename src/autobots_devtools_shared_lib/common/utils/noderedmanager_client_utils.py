"""HTTP client utilities for the Node-RED instance manager server REST API."""

import os

import httpx

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.trace_propagation import traced_http_call

logger = get_logger(__name__)

NODE_RED_MANAGER_HOST = os.getenv("NODE_RED_MANAGER_HOST", "localhost")


def _http_error_str(prefix: str, e: httpx.HTTPStatusError) -> str:
    """Format an HTTPStatusError into a standardised error string.

    Parses the JSON body to include the server's error_code (if present) so
    consumers can compare against exception constants without re-raising:

        if FlowsFileNotFoundError.ERROR_CODE in result: ...
    """
    try:
        body = e.response.json()
        error_code = body.get("error_code", "")
        detail = body.get("detail", e.response.text)
    except Exception:
        error_code = ""
        detail = e.response.text
    code_part = f" [{error_code}]" if error_code else ""
    return f"Error {prefix}: HTTP {e.response.status_code}{code_part} - {detail}"


NODE_RED_MANAGER_PORT = os.getenv("NODE_RED_MANAGER_PORT", "9003")
NODE_RED_MANAGER_BASE_URL = f"http://{NODE_RED_MANAGER_HOST}:{NODE_RED_MANAGER_PORT}"


def get_health(session_id: str | None = None) -> str:
    """
    Get the health status of the Node-RED manager server.

    Args:
        session_id: Optional session ID for trace correlation.

    Returns:
        String representation of health info (status, running_instances, available_environments).
    """
    logger.info("Getting Node-RED manager health")
    try:
        with (
            traced_http_call("noderedManagerGetHealth", session_id=session_id) as trace_headers,
            httpx.Client() as client,
        ):
            response = client.get(
                f"{NODE_RED_MANAGER_BASE_URL}/health",
                headers=trace_headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as e:
        logger.exception(
            "HTTP error getting Node-RED manager health: %s - %s",
            e.response.status_code,
            e.response.text,
        )
        return _http_error_str("getting health", e)
    except Exception as e:
        logger.exception("Error getting Node-RED manager health")
        return f"Error getting health: {e!s}"
    else:
        logger.info("Node-RED manager health: %s", result.get("status"))
        return str(result)


def list_instances(session_id: str | None = None) -> str:
    """
    List all currently running Node-RED instances.

    Args:
        session_id: Optional session ID for trace correlation.

    Returns:
        String representation of the instances list with count.
    """
    logger.info("Listing Node-RED instances")
    try:
        with (
            traced_http_call("noderedManagerListInstances", session_id=session_id) as trace_headers,
            httpx.Client() as client,
        ):
            response = client.get(
                f"{NODE_RED_MANAGER_BASE_URL}/instances",
                headers=trace_headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as e:
        logger.exception(
            "HTTP error listing Node-RED instances: %s - %s",
            e.response.status_code,
            e.response.text,
        )
        return _http_error_str("listing instances", e)
    except Exception as e:
        logger.exception("Error listing Node-RED instances")
        return f"Error listing instances: {e!s}"
    else:
        instances = result.get("instances", [])
        logger.info("Listed %d Node-RED instance(s)", len(instances))
        return str(result)


def create_instance(
    workspace_base_path: str,
    flows_json_path: str,
    environment_name: str,
    ttl_seconds: int | None = None,
    session_id: str | None = None,
) -> str:
    """
    Launch a new Node-RED instance (or return an existing one for the same workspace+environment).

    The instance ID is scoped as ``environment_name/workspace_base_path`` so the same workspace
    can run multiple environments simultaneously.

    Args:
        workspace_base_path: Workspace path (e.g. 'user/repo-JIRA-42').
        flows_json_path: Relative path to flows.json within the workspace directory.
        environment_name: Name of the Node-RED environment template to use.
        ttl_seconds: TTL in seconds before the instance is auto-killed. Uses server default if None.
        session_id: Optional session ID for trace correlation.

    Returns:
        Success message with instance id, url, and expiry time.
    """
    logger.info(
        "Creating Node-RED instance workspace=%r flows=%r environment=%r ttl=%s",
        workspace_base_path,
        flows_json_path,
        environment_name,
        ttl_seconds,
    )
    try:
        payload: dict = {
            "workspace_context": {"workspace_base_path": workspace_base_path},
            "flows_json_path": flows_json_path,
            "environment_name": environment_name,
        }
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        with (
            traced_http_call(
                "noderedManagerCreateInstance", session_id=session_id
            ) as trace_headers,
            httpx.Client() as client,
        ):
            response = client.post(
                f"{NODE_RED_MANAGER_BASE_URL}/create-instance",
                json=payload,
                headers=trace_headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as e:
        logger.exception(
            "HTTP error creating Node-RED instance workspace=%r: %s - %s",
            workspace_base_path,
            e.response.status_code,
            e.response.text,
        )
        return _http_error_str("creating instance", e)
    except Exception as e:
        logger.exception("Error creating Node-RED instance workspace=%r", workspace_base_path)
        return f"Error creating instance: {e!s}"
    else:
        logger.info(
            "Node-RED instance created/reused: id=%s url=%s expires_at=%s",
            result.get("id"),
            result.get("url"),
            result.get("expires_at"),
        )
        return f"Instance created: id={result['id']} url={result['url']} expires_at={result['expires_at']}"


def kill_instance(
    workspace_base_path: str,
    environment_name: str,
    session_id: str | None = None,
) -> str:
    """
    Kill a running Node-RED instance by workspace_base_path and environment_name.

    Args:
        workspace_base_path: Workspace path identifying the instance to kill.
        environment_name: Environment name of the instance to kill.
        session_id: Optional session ID for trace correlation.

    Returns:
        Success message from the server.
    """
    logger.info(
        "Killing Node-RED instance workspace=%r environment=%r",
        workspace_base_path,
        environment_name,
    )
    try:
        payload = {
            "workspace_context": {"workspace_base_path": workspace_base_path},
            "environment_name": environment_name,
        }
        with (
            traced_http_call("noderedManagerKillInstance", session_id=session_id) as trace_headers,
            httpx.Client() as client,
        ):
            response = client.post(
                f"{NODE_RED_MANAGER_BASE_URL}/kill-instance",
                json=payload,
                headers=trace_headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as e:
        logger.exception(
            "HTTP error killing Node-RED instance workspace=%r: %s - %s",
            workspace_base_path,
            e.response.status_code,
            e.response.text,
        )
        return _http_error_str("killing instance", e)
    except Exception as e:
        logger.exception(
            "Error killing Node-RED instance workspace=%r environment=%r",
            workspace_base_path,
            environment_name,
        )
        return f"Error killing instance: {e!s}"
    else:
        message = result.get("message", "Instance killed successfully")
        logger.info(
            "Node-RED instance killed workspace=%r environment=%r: %s",
            workspace_base_path,
            environment_name,
            message,
        )
        return message
