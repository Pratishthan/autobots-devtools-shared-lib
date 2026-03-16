# ABOUTME: Shared constants for all Jenkins integration files.
# ABOUTME: Single source of truth for default values, magic numbers, and string literals.

from __future__ import annotations

# ---------------------------------------------------------------------------
# Authentication defaults
# ---------------------------------------------------------------------------

DEFAULT_USERNAME_ENV: str = "JENKINS_USERNAME"
DEFAULT_API_TOKEN_ENV: str = "JENKINS_API_TOKEN"  # noqa: S105

# ---------------------------------------------------------------------------
# Polling defaults
# ---------------------------------------------------------------------------

DEFAULT_WAIT_FOR_COMPLETION: bool = True
DEFAULT_POLL_INTERVAL_SECONDS: int = 10
DEFAULT_MAX_WAIT_SECONDS: int = 300
DEFAULT_QUEUE_MAX_RETRIES: int = 5
DEFAULT_QUEUE_RETRY_DELAY_SECONDS: int = 2

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

HTTP_TIMEOUT_SECONDS: int = 30
QUEUE_INITIAL_DELAY_SECONDS: int = 1

# ---------------------------------------------------------------------------
# Jenkins API paths / URL segments
# ---------------------------------------------------------------------------

JENKINS_CONFIG_FILENAME: str = "jenkins.yaml"
API_JSON_SUFFIX: str = "api/json"
JOB_URL_SEGMENT: str = "job"
LAST_BUILD_SEGMENT: str = "lastBuild"
CONSOLE_LOG_PATH: str = "logText/progressiveText"

# ---------------------------------------------------------------------------
# URL templates  (use .format(base_url=..., job_name=..., build_number=..., start=...))
# ---------------------------------------------------------------------------

_BASE_JOB_PREFIX: str = "{base_url}/" + JOB_URL_SEGMENT + "/{job_name}/"

BUILD_STATUS_LATEST_URL: str = _BASE_JOB_PREFIX + LAST_BUILD_SEGMENT + "/" + API_JSON_SUFFIX
BUILD_STATUS_URL: str = _BASE_JOB_PREFIX + "{build_number}/" + API_JSON_SUFFIX
CONSOLE_LOG_LATEST_URL: str = (
    _BASE_JOB_PREFIX + LAST_BUILD_SEGMENT + "/" + CONSOLE_LOG_PATH + "?start={start}"
)
CONSOLE_LOG_URL: str = _BASE_JOB_PREFIX + "{build_number}/" + CONSOLE_LOG_PATH + "?start={start}"

# ---------------------------------------------------------------------------
# Tool naming
# ---------------------------------------------------------------------------

TOOL_NAME_SUFFIX: str = "_tool"
ARGS_SCHEMA_SUFFIX: str = "_args"

# ---------------------------------------------------------------------------
# Parameter config defaults
# ---------------------------------------------------------------------------

DEFAULT_PARAM_TYPE: str = "string"
DEFAULT_PARAM_REQUIRED: bool = True
