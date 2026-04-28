# ABOUTME: Low-level HTTP helpers for Jira REST API v3 interactions.
# ABOUTME: Handles auth resolution, subtask creation, status transitions, and subtask listing.

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.common.config.jira_config import JiraConfig

logger = get_logger(__name__)


def get_auth(config: JiraConfig) -> tuple[str, str] | None:
    """Resolve Basic Auth credentials from environment variables.

    Returns a (username, token) tuple, or None if either env var is unset.
    """
    username = os.environ.get(config.auth.username_env, "")
    token = os.environ.get(config.auth.token_env, "")
    if username and token:
        return (username, token)
    logger.warning(
        "Jira auth env vars '%s' / '%s' not set — requests will fail",
        config.auth.username_env,
        config.auth.token_env,
    )
    return None


def get_project_key(config: JiraConfig, parent_key: str) -> str:
    """Resolve the Jira project key from env or fall back to parsing parent_key."""
    return os.environ.get(config.project_key_env, "") or parent_key.split("-")[0]


def is_configured(config: JiraConfig) -> bool:
    """Return True if the minimum credentials are present to make Jira API calls."""
    return bool(
        config.base_url
        and os.environ.get(config.auth.username_env)
        and os.environ.get(config.auth.token_env)
    )


def make_client(config: JiraConfig) -> httpx.Client:
    """Build an httpx.Client configured for Jira REST API v3."""
    auth = get_auth(config)
    return httpx.Client(
        base_url=f"{config.base_url}/rest/api/3",
        auth=auth,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=config.http.timeout_seconds,
    )


def create_subtask(config: JiraConfig, parent_key: str, summary: str, description: str = "") -> str:
    """Create a Jira subtask under parent_key. Returns the new issue key."""
    payload: dict = {
        "fields": {
            "project": {"key": get_project_key(config, parent_key)},
            "parent": {"key": parent_key},
            "summary": summary,
            "issuetype": {"name": config.issue_types.subtask},
        }
    }
    if description:
        payload["fields"]["description"] = {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
        }
    with make_client(config) as c:
        resp = c.post("/issue", json=payload)
        resp.raise_for_status()
        return resp.json()["key"]


def update_issue_status(config: JiraConfig, issue_key: str, transition_name: str) -> None:
    """Transition issue_key to the named status (e.g. 'In Progress', 'Done')."""
    with make_client(config) as c:
        resp = c.get(f"/issue/{issue_key}/transitions")
        resp.raise_for_status()
        transitions = resp.json().get("transitions", [])
        match = next(
            (t for t in transitions if t["name"].lower() == transition_name.lower()), None
        )
        if not match:
            available = [t["name"] for t in transitions]
            raise ValueError(
                f"Transition '{transition_name}' not found for {issue_key}. Available: {available}"
            )
        c.post(
            f"/issue/{issue_key}/transitions", json={"transition": {"id": match["id"]}}
        ).raise_for_status()


def get_subtasks(config: JiraConfig, parent_key: str) -> list[dict]:
    """Return subtasks of parent_key as list of {key, summary, status}."""
    with make_client(config) as c:
        resp = c.get(f"/issue/{parent_key}", params={"fields": "subtasks"})
        resp.raise_for_status()
        subtasks = resp.json()["fields"].get("subtasks", [])
        return [
            {
                "key": s["key"],
                "summary": s["fields"]["summary"],
                "status": s["fields"]["status"]["name"],
            }
            for s in subtasks
        ]
