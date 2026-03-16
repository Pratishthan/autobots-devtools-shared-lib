# ABOUTME: Thin LangChain agent layer for Jenkins observability tools.
# ABOUTME: Wraps get_build_status() and get_console_log() from jenkins_builtin_utils as @tools.
# ABOUTME: All HTTP logic lives in common/utils/jenkins_builtin_utils.py.

from __future__ import annotations

from langchain.tools import tool

from autobots_devtools_shared_lib.common.utils.jenkins_builtin_utils import (
    get_build_status,
    get_console_log,
)


@tool
def get_jenkins_build_status(job_name: str, build_number: int | None = None) -> str:
    """Get the current status of a Jenkins build.

    Returns a concise string with job name, build number,
    status (SUCCESS / FAILURE / IN_PROGRESS), and build URL.
    Omit build_number to check the latest build.
    """
    return get_build_status(job_name, build_number)


@tool
def get_jenkins_console_log(job_name: str, build_number: int | None = None, start: int = 0) -> str:
    """Retrieve the console log output for a Jenkins build.

    Returns the log text from the given byte offset.
    Use start=0 (default) for the full log.
    Omit build_number to use the latest build.
    Useful for diagnosing pipeline failures.
    """
    return get_console_log(job_name, build_number, start)
