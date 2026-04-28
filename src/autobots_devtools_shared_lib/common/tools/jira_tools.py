# ABOUTME: LangChain agent tools for Jira subtask management.
# ABOUTME: register_jira_tools() is the single entry point — returns [] when jira.yaml is absent.
# ABOUTME: All HTTP logic lives in common/utils/jira_http_utils.py.

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


def _cfg():
    from autobots_devtools_shared_lib.common.config.jira_loader import get_jira_config

    cfg = get_jira_config()
    if cfg is None:
        raise RuntimeError(
            "Jira tools require jira.yaml but it was not found. "
            "Ensure DYNAGENT_CONFIG_ROOT_DIR points to a directory containing jira.yaml."
        )
    return cfg


@tool
def jira_create_subtask_tool(parent_key: str, summary: str, description: str = "") -> str:
    """Create a Jira subtask under the given parent issue.

    Args:
        parent_key: Parent Jira issue key (e.g. OPS-123).
        summary: Short title for the subtask.
        description: Optional longer description.

    Returns:
        The new subtask key (e.g. OPS-124).
    """
    from autobots_devtools_shared_lib.common.utils.jira_http_utils import create_subtask

    return create_subtask(_cfg(), parent_key, summary, description)


@tool
def jira_update_status_tool(issue_key: str, transition_name: str) -> str:
    """Transition a Jira issue to a new status.

    Args:
        issue_key: Jira issue key (e.g. OPS-124).
        transition_name: Target status name, e.g. 'In Progress' or 'Done'.

    Returns:
        Confirmation message.
    """
    from autobots_devtools_shared_lib.common.utils.jira_http_utils import update_issue_status

    update_issue_status(_cfg(), issue_key, transition_name)
    return f"{issue_key} transitioned to '{transition_name}'"


@tool
def jira_get_subtasks_tool(parent_key: str) -> list[dict]:
    """List all subtasks of a Jira issue with their current status.

    Args:
        parent_key: Parent Jira issue key (e.g. OPS-123).

    Returns:
        List of dicts with keys: key, summary, status.
    """
    from autobots_devtools_shared_lib.common.utils.jira_http_utils import get_subtasks

    return get_subtasks(_cfg(), parent_key)


def register_jira_tools() -> list[Any]:
    """Load jira.yaml and return all Jira tools.

    Returns an empty list when jira.yaml is absent — Jira integration is optional.
    """
    try:
        from autobots_devtools_shared_lib.common.config.jira_loader import get_jira_config

        if get_jira_config() is not None:
            tools = [jira_create_subtask_tool, jira_update_status_tool, jira_get_subtasks_tool]
            logger.info("Loaded %d Jira tools from jira.yaml", len(tools))
            return tools
    except Exception:
        logger.exception("Failed to load Jira tools — continuing without them")
    return []
