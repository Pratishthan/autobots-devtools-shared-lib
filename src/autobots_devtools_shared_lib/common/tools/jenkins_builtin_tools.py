# ABOUTME: Built-in generic Jenkins observability tools (LangChain @tool wrappers).
# ABOUTME: Provides get_jenkins_build_status and get_jenkins_console_log.
# ABOUTME: Call set_jenkins_config() once at startup before these tools are invoked.

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from langchain.tools import tool

from autobots_devtools_shared_lib.common.jenkins.http_utils import get_auth
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.common.jenkins.config import JenkinsConfig

logger = get_logger(__name__)

_config: JenkinsConfig | None = None


def set_jenkins_config(config: JenkinsConfig) -> None:
    """Store the Jenkins config for use by the builtin tools at call time."""
    global _config
    _config = config


def _get_config() -> JenkinsConfig:
    if _config is None:
        raise RuntimeError("Jenkins builtin tools used before set_jenkins_config() was called")
    return _config


@tool
def get_jenkins_build_status(job_name: str, build_number: int | None = None) -> str:
    """Get the current status of a Jenkins build.

    Returns a concise string with job name, build number,
    status (SUCCESS / FAILURE / IN_PROGRESS), and build URL.
    Omit build_number to check the latest build.
    """
    config = _get_config()
    base_url = config.base_url.rstrip("/")
    auth = get_auth(config)
    if build_number is None:
        api_url = f"{base_url}/job/{job_name}/lastBuild/api/json"
    else:
        api_url = f"{base_url}/job/{job_name}/{build_number}/api/json"
    try:
        resp = requests.get(api_url, auth=auth, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        number = data.get("number")
        building = data.get("building", False)
        result = data.get("result")
        url = data.get("url", "")
        status = "IN_PROGRESS" if (building or result is None) else str(result).upper()
    except requests.RequestException as exc:
        logger.exception(f"Error getting build status for '{job_name}'")
        return f"Error getting build status: {exc}"
    else:
        return f"job={job_name} build={number} status={status} url={url}"


@tool
def get_jenkins_console_log(job_name: str, build_number: int | None = None, start: int = 0) -> str:
    """Retrieve the console log output for a Jenkins build.

    Returns the log text from the given byte offset.
    Use start=0 (default) for the full log.
    Omit build_number to use the latest build.
    Useful for diagnosing pipeline failures.
    """
    config = _get_config()
    base_url = config.base_url.rstrip("/")
    auth = get_auth(config)
    if build_number is None:
        log_url = f"{base_url}/job/{job_name}/lastBuild/logText/progressiveText?start={start}"
    else:
        log_url = f"{base_url}/job/{job_name}/{build_number}/logText/progressiveText?start={start}"
    try:
        resp = requests.get(log_url, auth=auth, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.exception(f"Error getting console log for '{job_name}'")
        return f"Error getting console log: {exc}"
    else:
        return resp.text
