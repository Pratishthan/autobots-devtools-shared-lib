# ABOUTME: Pydantic models for jenkins.yaml configuration.
# ABOUTME: Defines auth, polling, parameter, tool, and top-level Jenkins config models.

from __future__ import annotations

from pydantic import BaseModel, Field


class JenkinsAuthConfig(BaseModel):
    """Credentials resolved from environment variables at runtime."""

    username_env: str = Field(
        default="JENKINS_USERNAME",
        description="Name of the env var holding the Jenkins username",
    )
    token_env: str = Field(
        default="JENKINS_API_TOKEN",
        description="Name of the env var holding the Jenkins API token",
    )


class JenkinsPollingConfig(BaseModel):
    """Controls whether and how long to wait for a triggered build to complete."""

    wait_for_completion: bool = Field(
        default=True,
        description="Whether to block until the build finishes",
    )
    poll_interval_seconds: int = Field(
        default=10,
        description="Seconds to wait between build-status polls",
    )
    max_wait_seconds: int = Field(
        default=300,
        description="Maximum seconds to wait before giving up",
    )
    queue_max_retries: int = Field(
        default=5,
        description="Max attempts to resolve a build number from the Jenkins queue",
    )
    queue_retry_delay_seconds: int = Field(
        default=2,
        description="Seconds to wait between queue-item polls",
    )


class JenkinsParameterConfig(BaseModel):
    """A single parameter that will be forwarded as a query string to Jenkins."""

    type: str = Field(
        default="string",
        description="Parameter type: 'string', 'boolean', or 'integer'",
    )
    description: str = Field(
        default="",
        description="LLM-facing hint describing what value to provide",
    )
    required: bool = Field(
        default=True,
        description="Whether the LLM must always supply this parameter",
    )


class JenkinsPipelineConfig(BaseModel):
    """Configuration for a single Jenkins pipeline entry.

    The framework registers this as a LangChain tool named ``{key}_tool``,
    so pipeline keys in jenkins.yaml should not carry a ``_tool`` suffix.
    """

    uri: str = Field(
        description="Relative URI path for the Jenkins pipeline, e.g. /job/my-job/buildWithParameters"
    )
    description: str = Field(
        default="",
        description="LLM-facing docstring describing what this pipeline does",
    )
    parameters: dict[str, JenkinsParameterConfig] = Field(
        default_factory=dict,
        description="Parameters forwarded as query strings to Jenkins",
    )
    polling: JenkinsPollingConfig | None = Field(
        default=None,
        description="Per-pipeline polling overrides; falls back to global polling config when None",
    )


class JenkinsConfig(BaseModel):
    """Top-level Jenkins configuration loaded from jenkins.yaml."""

    base_url: str = Field(description="Jenkins base URL, e.g. https://jenkins.example.com")
    auth: JenkinsAuthConfig = Field(
        default_factory=JenkinsAuthConfig,
        description="Authentication configuration (env var names for credentials)",
    )
    polling: JenkinsPollingConfig = Field(
        default_factory=JenkinsPollingConfig,
        description="Global polling defaults, overridable per pipeline",
    )
    pipelines: dict[str, JenkinsPipelineConfig] = Field(
        description=(
            "Named pipeline definitions. Each key is the pipeline identifier; "
            "the framework registers it as a LangChain tool named ``{key}_tool``."
        )
    )
