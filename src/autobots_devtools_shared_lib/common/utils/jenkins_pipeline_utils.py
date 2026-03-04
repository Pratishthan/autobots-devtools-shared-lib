# ABOUTME: Deterministic Jenkins pipeline runner — pure Python, no LangChain dependency.
# ABOUTME: JenkinsPipelineRunner wraps JenkinsConfig and exposes run() / get_callable().
# ABOUTME: Entry point for deterministic callers: get_pipeline_runner().run("pipeline_name", PARAM="value")

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from autobots_devtools_shared_lib.common.config.jenkins_constants import HTTP_TIMEOUT_SECONDS
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.utils.jenkins_http_utils import (
    extract_job_name_from_url,
    get_auth,
    poll_queue_for_build_number,
    wait_for_build,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from autobots_devtools_shared_lib.common.config.jenkins_config import (
        JenkinsConfig,
        JenkinsPipelineConfig,
    )

logger = get_logger(__name__)

_runner: JenkinsPipelineRunner | None = None


def get_pipeline_runner() -> JenkinsPipelineRunner:
    """Return the shared JenkinsPipelineRunner, creating it from jenkins.yaml on first call.

    This is the **primary entry point** for deterministic (non-agent) callers that need
    to trigger Jenkins pipelines directly from Python code.

    The runner is a module-level singleton — config is read from disk once and cached.
    No setup or explicit initialisation is required before calling this function.

    Usage::

        from autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils import (
            get_pipeline_runner,
        )

        # Trigger a pipeline by name — parameter keys match jenkins.yaml exactly
        result = get_pipeline_runner().run("create_workspace", WORKSPACE_NAME="my-ws", USER_ID="u1")

        # Or bind a specific pipeline to a variable / pass it into a flow
        trigger = get_pipeline_runner().get_callable("create_workspace")
        result = trigger(WORKSPACE_NAME="my-ws", USER_ID="u1")

    Prerequisites:
        - ``DYNAGENT_CONFIG_ROOT_DIR`` env var must point to a directory containing
          ``jenkins.yaml`` (the same directory as ``agents.yaml``).
        - ``JENKINS_USERNAME`` and ``JENKINS_API_TOKEN`` env vars must be set for
          authenticated requests (default env var names; configurable in jenkins.yaml).

    Raises:
        RuntimeError: If jenkins.yaml cannot be found. Check that DYNAGENT_CONFIG_ROOT_DIR
                      is set and the file exists in the config directory.
    """
    global _runner
    if _runner is None:
        from autobots_devtools_shared_lib.common.config.jenkins_loader import get_jenkins_config

        config = get_jenkins_config()
        if config is None:
            raise RuntimeError(
                "JenkinsPipelineRunner requires jenkins.yaml but it was not found. "
                "Ensure DYNAGENT_CONFIG_ROOT_DIR points to a directory containing jenkins.yaml."
            )
        _runner = JenkinsPipelineRunner(config)
    return _runner


def _execute_pipeline(
    config: JenkinsConfig,
    pipeline_name: str,
    pipeline_cfg: JenkinsPipelineConfig,
    **kwargs: Any,
) -> str:
    """Trigger a Jenkins pipeline and optionally wait for it to complete.

    This is the single implementation shared by both the deterministic caller
    (JenkinsPipelineRunner) and the LangChain StructuredTool wrappers.

    Args:
        config: Top-level JenkinsConfig (base URL, auth, global polling).
        pipeline_name: Human-readable identifier used only for log messages.
        pipeline_cfg: The per-pipeline config entry from jenkins.yaml.
        **kwargs: Pipeline parameters forwarded as query-string values to Jenkins.
                  Keys must match the ``parameters`` block in jenkins.yaml.

    Returns:
        A status string — either build URL on fire-and-forget, or final build
        result (SUCCESS/FAILURE/…) when wait_for_completion is True.
    """
    effective_polling = pipeline_cfg.polling or config.polling
    full_url = config.base_url.rstrip("/") + pipeline_cfg.uri
    auth = get_auth(config)
    query_params = {k: v for k, v in kwargs.items() if v is not None}

    logger.info(
        "Triggering Jenkins pipeline '%s': POST %s params=%s",
        pipeline_name,
        full_url,
        query_params,
    )
    try:
        response = requests.post(
            full_url, params=query_params, auth=auth, timeout=HTTP_TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Jenkins trigger failed for '%s'", pipeline_name)
        return f"Error triggering Jenkins pipeline: {exc}"

    queue_location = response.headers.get("Location", "")
    build_info = poll_queue_for_build_number(queue_location, effective_polling, auth)

    if build_info["status"] != "success":
        return build_info["message"]

    build_number: int = build_info["build_number"]
    build_url: str = build_info["build_url"]

    if not effective_polling.wait_for_completion:
        logger.info("Fire-and-forget: build #%s triggered at %s", build_number, build_url)
        return f"Build #{build_number} triggered: {build_url}"

    job_name = extract_job_name_from_url(pipeline_cfg.uri)
    return wait_for_build(config.base_url, job_name, build_number, effective_polling, auth)


class JenkinsPipelineRunner:
    """Executes Jenkins pipelines defined in jenkins.yaml directly from Python code.

    Do not instantiate this class directly — use ``get_pipeline_runner()`` to get
    the shared singleton instance that is auto-configured from jenkins.yaml.

    Two invocation styles are supported:

    **Style 1 — call by name (inline):**

        result = get_pipeline_runner().run("create_workspace", WORKSPACE_NAME="my-ws", USER_ID="u1")

    **Style 2 — bind to a variable (useful in flows):**

        create_ws = get_pipeline_runner().get_callable("create_workspace")
        result = create_ws(WORKSPACE_NAME="my-ws", USER_ID="u1")

    Parameter names (``WORKSPACE_NAME``, ``USER_ID``, …) must match the keys defined
    under ``parameters:`` in ``jenkins.yaml`` for the chosen pipeline.

    Both styles return a status string:
    - Fire-and-forget pipelines: ``"Build #<n> triggered: <url>"``
    - Wait-for-completion pipelines: ``"job=<name> build=<n> result=<STATUS> url=<url>"``
    - On error: ``"Error triggering Jenkins pipeline: <detail>"``
    """

    def __init__(self, config: JenkinsConfig) -> None:
        self._config = config

    def run(self, pipeline_name: str, **kwargs: Any) -> str:
        """Trigger a Jenkins pipeline by name with the given parameters.

        Args:
            pipeline_name: Key from the ``pipelines`` block in jenkins.yaml
                           (e.g. ``"create_workspace"``).
            **kwargs: Parameter values forwarded to Jenkins as query-string entries.
                      Keys must match the ``parameters`` block for the chosen pipeline.

        Returns:
            Status string from Jenkins (build URL or final result).

        Raises:
            ValueError: If ``pipeline_name`` is not found in the loaded config.
        """
        pipeline_cfg = self._config.pipelines.get(pipeline_name)
        if pipeline_cfg is None:
            available = ", ".join(self._config.pipelines)
            raise ValueError(
                f"Unknown pipeline '{pipeline_name}'. Available pipelines: {available}"
            )
        return _execute_pipeline(self._config, pipeline_name, pipeline_cfg, **kwargs)

    def get_callable(self, pipeline_name: str) -> Callable[..., str]:
        """Return a bound callable for a specific pipeline.

        Useful for assigning pipeline triggers to variables or passing them
        into flow orchestration code without keeping a reference to the runner.

        Args:
            pipeline_name: Key from the ``pipelines`` block in jenkins.yaml.

        Returns:
            A callable ``(**kwargs) -> str`` that triggers the named pipeline.

        Raises:
            ValueError: If ``pipeline_name`` is not found in the loaded config
                        (validated eagerly at call time, not at invocation time).
        """
        pipeline_cfg = self._config.pipelines.get(pipeline_name)
        if pipeline_cfg is None:
            available = ", ".join(self._config.pipelines)
            raise ValueError(
                f"Unknown pipeline '{pipeline_name}'. Available pipelines: {available}"
            )

        def _call(**kwargs: Any) -> str:
            return _execute_pipeline(self._config, pipeline_name, pipeline_cfg, **kwargs)

        _call.__name__ = f"{pipeline_name}_trigger"  # cosmetic only — not used by StructuredTool
        return _call
