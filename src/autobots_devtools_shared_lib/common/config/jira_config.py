# ABOUTME: Pydantic models for jira.yaml configuration.
# ABOUTME: Mirrors the Jenkins config pattern: auth, http, issue-type, and transition settings.

from __future__ import annotations

from pydantic import BaseModel, Field

JIRA_CONFIG_FILENAME = "jira.yaml"

DEFAULT_USERNAME_ENV = "JIRA_USERNAME"
DEFAULT_TOKEN_ENV = "JIRA_API_TOKEN"
DEFAULT_PROJECT_KEY_ENV = "JIRA_PROJECT_KEY"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_SUBTASK_TYPE = "Subtask"
DEFAULT_IN_PROGRESS = "In Progress"
DEFAULT_DONE = "Done"


class JiraAuthConfig(BaseModel):
    """Credentials resolved from environment variables at runtime."""

    username_env: str = Field(
        default=DEFAULT_USERNAME_ENV,
        description="Name of the env var holding the Jira username/email",
    )
    token_env: str = Field(
        default=DEFAULT_TOKEN_ENV,
        description="Name of the env var holding the Jira API token",
    )


class JiraHttpConfig(BaseModel):
    """HTTP client settings for Jira API calls."""

    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        description="Request timeout in seconds",
    )


class JiraIssueTypesConfig(BaseModel):
    """Issue type names as configured in the target Jira project."""

    subtask: str = Field(
        default=DEFAULT_SUBTASK_TYPE,
        description="Issue type name for subtasks (must match the project's scheme)",
    )


class JiraTransitionsConfig(BaseModel):
    """Canonical transition names used to move issues between statuses."""

    in_progress: str = Field(
        default=DEFAULT_IN_PROGRESS,
        description="Transition name that moves an issue to In Progress",
    )
    done: str = Field(
        default=DEFAULT_DONE,
        description="Transition name that moves an issue to Done",
    )


class JiraConfig(BaseModel):
    """Top-level Jira configuration loaded from jira.yaml."""

    base_url: str = Field(description="Jira base URL, e.g. https://acme.atlassian.net")
    auth: JiraAuthConfig = Field(
        default_factory=JiraAuthConfig,
        description="Authentication configuration (env var names for credentials)",
    )
    project_key_env: str = Field(
        default=DEFAULT_PROJECT_KEY_ENV,
        description="Name of the env var holding the default Jira project key",
    )
    http: JiraHttpConfig = Field(
        default_factory=JiraHttpConfig,
        description="HTTP client settings",
    )
    issue_types: JiraIssueTypesConfig = Field(
        default_factory=JiraIssueTypesConfig,
        description="Issue type names as configured in the target Jira project",
    )
    transitions: JiraTransitionsConfig = Field(
        default_factory=JiraTransitionsConfig,
        description="Canonical transition names for status changes",
    )
