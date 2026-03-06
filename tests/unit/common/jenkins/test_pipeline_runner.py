# ABOUTME: Unit tests for JenkinsPipelineRunner and get_pipeline_runner() singleton.
# ABOUTME: All HTTP calls are mocked — tests cover routing, validation, and trigger behaviour.

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import autobots_devtools_shared_lib.common.config.jenkins_loader as jenkins_loader_module
import autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils as pipeline_utils_module
from autobots_devtools_shared_lib.common.config.jenkins_config import (
    JenkinsConfig,
    JenkinsParameterConfig,
    JenkinsPipelineConfig,
    JenkinsPollingConfig,
)
from autobots_devtools_shared_lib.common.config.jenkins_loader import set_jenkins_config
from autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils import (
    JenkinsPipelineRunner,
    get_pipeline_runner,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIRE_AND_FORGET_POLLING = JenkinsPollingConfig(
    wait_for_completion=False,
    queue_max_retries=2,
    queue_retry_delay_seconds=0,
)

_WAIT_POLLING = JenkinsPollingConfig(
    wait_for_completion=True,
    poll_interval_seconds=1,
    max_wait_seconds=10,
    queue_max_retries=2,
    queue_retry_delay_seconds=0,
)


@pytest.fixture
def cfg_fire_and_forget() -> JenkinsConfig:
    """Config with a single pipeline in fire-and-forget mode."""
    return JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={
            "create_workspace": JenkinsPipelineConfig(
                uri="/job/create-workspace/buildWithParameters",
                description="Create a workspace",
                polling=_FIRE_AND_FORGET_POLLING,
                parameters={
                    "WORKSPACE_NAME": JenkinsParameterConfig(
                        type="string", description="Workspace name", required=True
                    ),
                    "USER_ID": JenkinsParameterConfig(
                        type="string", description="User ID", required=True
                    ),
                },
            )
        },
    )


@pytest.fixture
def cfg_wait() -> JenkinsConfig:
    """Config with a single pipeline that waits for completion."""
    return JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={
            "build_workspace": JenkinsPipelineConfig(
                uri="/job/build-workspace/buildWithParameters",
                description="Build workspace",
                polling=_WAIT_POLLING,
                parameters={
                    "WORKSPACE_NAME": JenkinsParameterConfig(
                        type="string", description="Workspace name", required=True
                    ),
                },
            )
        },
    )


@pytest.fixture
def runner_faf(cfg_fire_and_forget) -> JenkinsPipelineRunner:
    return JenkinsPipelineRunner(cfg_fire_and_forget)


@pytest.fixture
def runner_wait(cfg_wait) -> JenkinsPipelineRunner:
    return JenkinsPipelineRunner(cfg_wait)


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch):
    """Isolate module-level singletons between tests."""
    monkeypatch.setattr(pipeline_utils_module, "_runner", None)
    monkeypatch.setattr(jenkins_loader_module, "_config", None)
    monkeypatch.setattr(jenkins_loader_module, "_config_loaded", False)
    yield


# ---------------------------------------------------------------------------
# JenkinsPipelineRunner — routing and validation (no HTTP)
# ---------------------------------------------------------------------------


def test_run_raises_value_error_for_unknown_pipeline(runner_faf):
    with pytest.raises(ValueError, match="Unknown pipeline 'nonexistent'"):
        runner_faf.run("nonexistent")


def test_run_error_message_lists_available_pipelines(runner_faf):
    with pytest.raises(ValueError, match="create_workspace"):
        runner_faf.run("nonexistent")


def test_get_callable_raises_value_error_for_unknown_pipeline(runner_faf):
    with pytest.raises(ValueError, match="Unknown pipeline 'nonexistent'"):
        runner_faf.get_callable("nonexistent")


def test_get_callable_validates_eagerly_before_invocation(runner_faf):
    """ValueError is raised at get_callable() time, not at call time."""
    with pytest.raises(ValueError):
        runner_faf.get_callable("does_not_exist")


def test_get_callable_returns_callable(runner_faf):
    fn = runner_faf.get_callable("create_workspace")
    assert callable(fn)


def test_get_callable_function_name(runner_faf):
    fn = runner_faf.get_callable("create_workspace")
    assert fn.__name__ == "create_workspace_trigger"


# ---------------------------------------------------------------------------
# _execute_pipeline via run() — fire-and-forget path
# ---------------------------------------------------------------------------


def _mock_post_response(location: str = "https://ci.example.com/queue/item/99/") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.headers = {"Location": location}
    return resp


def _queue_success(build_number: int = 42) -> dict:
    return {
        "status": "success",
        "message": f"Build #{build_number} assigned",
        "build_number": build_number,
        "build_url": f"https://ci.example.com/job/create-workspace/{build_number}/",
    }


def test_run_fire_and_forget_returns_build_triggered_string(runner_faf):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = _queue_success(42)

        result = runner_faf.run("create_workspace", WORKSPACE_NAME="my-ws", USER_ID="u1")

    assert "Build #42 triggered" in result
    assert "https://ci.example.com/job/create-workspace/42/" in result


def test_run_forwards_kwargs_as_query_params(runner_faf):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = _queue_success()

        runner_faf.run("create_workspace", WORKSPACE_NAME="ws-123", USER_ID="u99")

    _, call_kwargs = mock_post.call_args
    params = call_kwargs.get("params", {})
    assert params.get("WORKSPACE_NAME") == "ws-123"
    assert params.get("USER_ID") == "u99"


def test_run_strips_none_kwargs_from_params(runner_faf):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = _queue_success()

        runner_faf.run("create_workspace", WORKSPACE_NAME="ws-1", USER_ID=None)

    _, call_kwargs = mock_post.call_args
    params = call_kwargs.get("params", {})
    assert "USER_ID" not in params


def test_run_uses_correct_trigger_url(runner_faf):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = _queue_success()

        runner_faf.run("create_workspace", WORKSPACE_NAME="ws", USER_ID="u1")

    url_called = mock_post.call_args[0][0]
    assert url_called == "https://ci.example.com/job/create-workspace/buildWithParameters"


# ---------------------------------------------------------------------------
# _execute_pipeline via run() — wait-for-completion path
# ---------------------------------------------------------------------------


def test_run_wait_for_completion_returns_build_result(runner_wait):
    expected_result = "job=build-workspace build=7 result=SUCCESS url=https://ci.example.com/job/build-workspace/7/"
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.wait_for_build"
        ) as mock_wait,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = {
            "status": "success",
            "message": "Build #7 assigned",
            "build_number": 7,
            "build_url": "https://ci.example.com/job/build-workspace/7/",
        }
        mock_wait.return_value = expected_result

        result = runner_wait.run("build_workspace", WORKSPACE_NAME="ws-1")

    assert result == expected_result


def test_run_wait_for_completion_calls_wait_for_build_with_correct_args(runner_wait):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.wait_for_build"
        ) as mock_wait,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = {
            "status": "success",
            "message": "ok",
            "build_number": 5,
            "build_url": "https://ci.example.com/job/build-workspace/5/",
        }
        mock_wait.return_value = "result"

        runner_wait.run("build_workspace", WORKSPACE_NAME="ws")

    mock_wait.assert_called_once()
    args = mock_wait.call_args[0]
    assert args[0] == "https://ci.example.com"  # base_url
    assert args[1] == "build-workspace"  # job_name extracted from URI
    assert args[2] == 5  # build_number


# ---------------------------------------------------------------------------
# _execute_pipeline — error paths
# ---------------------------------------------------------------------------


def test_run_returns_error_string_on_http_failure(runner_faf):
    with patch(
        "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
    ) as mock_post:
        mock_post.side_effect = requests.ConnectionError("connection refused")

        result = runner_faf.run("create_workspace", WORKSPACE_NAME="ws", USER_ID="u1")

    assert result.startswith("Error triggering Jenkins pipeline:")
    assert "connection refused" in result


def test_run_returns_error_string_on_http_status_error(runner_faf):
    with patch(
        "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
    ) as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_post.return_value = mock_resp

        result = runner_faf.run("create_workspace", WORKSPACE_NAME="ws", USER_ID="u1")

    assert result.startswith("Error triggering Jenkins pipeline:")


def test_run_returns_queued_message_when_queue_not_resolved(runner_faf):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = {
            "status": "queued",
            "message": "Build queued but not yet assigned after 2 attempts",
            "build_number": None,
            "build_url": None,
        }

        result = runner_faf.run("create_workspace", WORKSPACE_NAME="ws", USER_ID="u1")

    assert "queued" in result.lower()


# ---------------------------------------------------------------------------
# get_callable — delegates to same execution as run()
# ---------------------------------------------------------------------------


def test_get_callable_result_matches_run(runner_faf):
    with (
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.requests.post"
        ) as mock_post,
        patch(
            "autobots_devtools_shared_lib.common.utils.jenkins_pipeline_utils.poll_queue_for_build_number"
        ) as mock_poll,
    ):
        mock_post.return_value = _mock_post_response()
        mock_poll.return_value = _queue_success(10)

        fn = runner_faf.get_callable("create_workspace")
        result = fn(WORKSPACE_NAME="ws", USER_ID="u1")

    assert "Build #10 triggered" in result


# ---------------------------------------------------------------------------
# get_pipeline_runner() — singleton behaviour
# ---------------------------------------------------------------------------


def test_get_pipeline_runner_raises_when_no_config(tmp_path, monkeypatch):
    """No jenkins.yaml → RuntimeError."""
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: tmp_path,
    )
    with pytest.raises(RuntimeError, match=r"jenkins\.yaml"):
        get_pipeline_runner()


def test_get_pipeline_runner_returns_runner_when_config_injected(cfg_fire_and_forget):
    set_jenkins_config(cfg_fire_and_forget)
    runner = get_pipeline_runner()
    assert isinstance(runner, JenkinsPipelineRunner)


def test_get_pipeline_runner_is_cached(cfg_fire_and_forget):
    """Multiple calls return the exact same instance."""
    set_jenkins_config(cfg_fire_and_forget)
    first = get_pipeline_runner()
    second = get_pipeline_runner()
    assert first is second


def test_get_pipeline_runner_config_matches_injected(cfg_fire_and_forget):
    set_jenkins_config(cfg_fire_and_forget)
    runner = get_pipeline_runner()
    assert runner._config.base_url == "https://ci.example.com"
    assert "create_workspace" in runner._config.pipelines
