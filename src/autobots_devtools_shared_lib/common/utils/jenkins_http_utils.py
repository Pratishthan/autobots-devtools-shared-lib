# ABOUTME: Low-level HTTP helpers for Jenkins API interactions.
# ABOUTME: Handles auth resolution, queue polling, build completion waiting, and URL parsing.

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

import requests

from autobots_devtools_shared_lib.common.config.jenkins_constants import (
    API_JSON_SUFFIX,
    BUILD_STATUS_URL,
    HTTP_TIMEOUT_SECONDS,
    JOB_URL_SEGMENT,
    QUEUE_INITIAL_DELAY_SECONDS,
)
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.common.config.jenkins_config import (
        JenkinsConfig,
        JenkinsPollingConfig,
    )

logger = get_logger(__name__)


def get_auth(config: JenkinsConfig) -> tuple[str, str] | None:
    """Resolve Basic Auth credentials from environment variables.

    Returns a (username, token) tuple, or None if either env var is unset.
    """
    username = os.getenv(config.auth.username_env, "")
    token = os.getenv(config.auth.token_env, "")
    if username and token:
        return (username, token)
    logger.warning(
        f"Jenkins auth env vars '{config.auth.username_env}' / '{config.auth.token_env}' "
        "not set — requests will be unauthenticated"
    )
    return None


def poll_queue_for_build_number(
    queue_location: str,
    polling: JenkinsPollingConfig,
    auth: tuple[str, str] | None,
) -> dict[str, Any]:
    """Poll the Jenkins queue API until a build number is assigned.

    Returns a dict with keys: status ('success' | 'queued' | 'error'),
    message, build_number, build_url.
    """
    if not queue_location:
        msg = "No queue location returned — build may not have triggered"
        logger.error(msg)
        return {"status": "error", "message": msg, "build_number": None, "build_url": None}

    time.sleep(QUEUE_INITIAL_DELAY_SECONDS)
    queue_api_url = f"{queue_location}{API_JSON_SUFFIX}"
    logger.info(f"Polling Jenkins queue: {queue_api_url}")

    for attempt in range(polling.queue_max_retries):
        try:
            resp = requests.get(queue_api_url, auth=auth, timeout=HTTP_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            executable = data.get("executable")
            if executable:
                build_number = executable.get("number")
                build_url = executable.get("url")
                logger.info(f"Build #{build_number} assigned: {build_url}")
                return {
                    "status": "success",
                    "message": f"Build #{build_number} assigned",
                    "build_number": build_number,
                    "build_url": build_url,
                }
            if attempt < polling.queue_max_retries - 1:
                logger.debug(
                    f"Queue attempt {attempt + 1}/{polling.queue_max_retries}: "
                    f"build not yet assigned, waiting {polling.queue_retry_delay_seconds}s"
                )
                time.sleep(polling.queue_retry_delay_seconds)
        except requests.RequestException as exc:
            logger.exception(f"Queue poll error (attempt {attempt + 1})")
            if attempt < polling.queue_max_retries - 1:
                time.sleep(polling.queue_retry_delay_seconds)
            else:
                return {
                    "status": "error",
                    "message": f"Queue poll failed after {polling.queue_max_retries} attempts: {exc}",
                    "build_number": None,
                    "build_url": None,
                }

    return {
        "status": "queued",
        "message": f"Build queued but not yet assigned after {polling.queue_max_retries} attempts",
        "build_number": None,
        "build_url": None,
    }


def wait_for_build(
    base_url: str,
    job_name: str,
    build_number: int,
    polling: JenkinsPollingConfig,
    auth: tuple[str, str] | None,
) -> str:
    """Poll the build API until the result is non-null or the timeout is reached."""
    elapsed = 0
    api_url = BUILD_STATUS_URL.format(
        base_url=base_url, job_name=job_name, build_number=build_number
    )
    while elapsed < polling.max_wait_seconds:
        try:
            resp = requests.get(api_url, auth=auth, timeout=HTTP_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            building = data.get("building", False)
            result = data.get("result")
            build_url = data.get("url", "")
            if not building and result is not None:
                logger.info(f"Build #{build_number} completed: {result}")
                return f"job={job_name} build={build_number} result={result} url={build_url}"
            logger.debug(
                f"Build #{build_number} in progress; "
                f"waiting {polling.poll_interval_seconds}s (elapsed={elapsed}s)"
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            logger.warning(
                f"Transient poll error for {job_name}#{build_number}: {exc}; retrying in "
                f"{polling.poll_interval_seconds}s (elapsed={elapsed}s)"
            )
        except requests.HTTPError as exc:
            logger.exception(f"HTTP error polling {job_name}#{build_number}")
            return f"Error polling build status: {exc}"
        except requests.RequestException as exc:
            logger.exception(f"Unexpected poll error for {job_name}#{build_number}")
            return f"Error polling build status: {exc}"
        time.sleep(polling.poll_interval_seconds)
        elapsed += polling.poll_interval_seconds
    return (
        f"Timeout: build #{build_number} for job '{job_name}' "
        f"did not complete within {polling.max_wait_seconds}s"
    )


def extract_job_name_from_url(url: str) -> str:
    """Extract the Jenkins job name from a relative URL.

    Example: /job/create-workspace/buildWithParameters → 'create-workspace'
    """
    parts = [p for p in url.split("/") if p]
    try:
        job_idx = parts.index(JOB_URL_SEGMENT)
        return parts[job_idx + 1]
    except (ValueError, IndexError):
        return url
