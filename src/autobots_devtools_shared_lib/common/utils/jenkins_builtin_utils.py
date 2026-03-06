# ABOUTME: Deterministic Jenkins observability utilities — pure Python, no LangChain dependency.
# ABOUTME: Provides get_build_status() and get_console_log() for direct/deterministic use.
# ABOUTME: LangChain @tool wrappers live in common/tools/jenkins_builtin_tools.py.

from __future__ import annotations

import requests

from autobots_devtools_shared_lib.common.config.jenkins_constants import (
    BUILD_STATUS_LATEST_URL,
    BUILD_STATUS_URL,
    CONSOLE_LOG_LATEST_URL,
    CONSOLE_LOG_URL,
    HTTP_TIMEOUT_SECONDS,
)
from autobots_devtools_shared_lib.common.config.jenkins_loader import get_jenkins_config
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.jenkins_http_utils import get_auth

logger = get_logger(__name__)


def get_build_status(job_name: str, build_number: int | None = None) -> str:
    """Get the current status of a Jenkins build.

    Args:
        job_name: Jenkins job name.
        build_number: Specific build number; omit to check the latest build.

    Returns:
        A concise string: ``job=<name> build=<n> status=<STATUS> url=<url>``.
        Returns an error string if Jenkins is not configured or the request fails.
    """
    config = get_jenkins_config()
    if config is None:
        return "Error: Jenkins is not configured (jenkins.yaml not found)"

    base_url = config.base_url.rstrip("/")
    auth = get_auth(config)
    if build_number is None:
        api_url = BUILD_STATUS_LATEST_URL.format(base_url=base_url, job_name=job_name)
    else:
        api_url = BUILD_STATUS_URL.format(
            base_url=base_url, job_name=job_name, build_number=build_number
        )

    logger.info("Getting build status for job='%s' build=%s", job_name, build_number)
    try:
        resp = requests.get(api_url, auth=auth, timeout=HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        number = data.get("number")
        building = data.get("building", False)
        result = data.get("result")
        url = data.get("url", "")
        status = "IN_PROGRESS" if (building or result is None) else str(result).upper()
    except requests.RequestException as exc:
        logger.exception("Error getting build status for '%s'", job_name)
        return f"Error getting build status: {exc}"
    else:
        return f"job={job_name} build={number} status={status} url={url}"


def get_console_log(job_name: str, build_number: int | None = None, start: int = 0) -> str:
    """Retrieve the console log output for a Jenkins build.

    Args:
        job_name: Jenkins job name.
        build_number: Specific build number; omit to use the latest build.
        start: Byte offset to start reading from (0 for the full log).

    Returns:
        Log text as a string.
        Returns an error string if Jenkins is not configured or the request fails.
    """
    config = get_jenkins_config()
    if config is None:
        return "Error: Jenkins is not configured (jenkins.yaml not found)"

    base_url = config.base_url.rstrip("/")
    auth = get_auth(config)
    if build_number is None:
        log_url = CONSOLE_LOG_LATEST_URL.format(base_url=base_url, job_name=job_name, start=start)
    else:
        log_url = CONSOLE_LOG_URL.format(
            base_url=base_url, job_name=job_name, build_number=build_number, start=start
        )

    logger.info("Getting console log for job='%s' build=%s start=%s", job_name, build_number, start)
    try:
        resp = requests.get(log_url, auth=auth, timeout=HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Error getting console log for '%s'", job_name)
        return f"Error getting console log: {exc}"
    else:
        return resp.text
