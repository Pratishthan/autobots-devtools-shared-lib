# ABOUTME: Unit tests for Jenkins HTTP utility helpers.
# ABOUTME: Covers extract_job_name_from_url (pure) and get_auth (env-var-driven).

from __future__ import annotations

import pytest

from autobots_devtools_shared_lib.common.config.jenkins_config import (
    JenkinsAuthConfig,
    JenkinsConfig,
)
from autobots_devtools_shared_lib.common.utils.jenkins_http_utils import (
    extract_job_name_from_url,
    get_auth,
)

# ---------------------------------------------------------------------------
# extract_job_name_from_url — pure function, no mocking needed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("/job/create-workspace/buildWithParameters", "create-workspace"),
        ("/job/deploy-app/build", "deploy-app"),
        ("/job/my-job/", "my-job"),
        ("/job/run-tests/buildWithParameters", "run-tests"),
        # Nested path — still extracts the segment right after /job/
        ("/prefix/job/some-job/buildWithParameters", "some-job"),
    ],
)
def test_extract_job_name_standard_paths(uri, expected):
    assert extract_job_name_from_url(uri) == expected


def test_extract_job_name_no_job_segment_returns_input():
    """When the URI has no /job/ segment the original string is returned unchanged."""
    bad_uri = "not-a-job-url"
    assert extract_job_name_from_url(bad_uri) == bad_uri


def test_extract_job_name_empty_string_returns_empty():
    assert extract_job_name_from_url("") == ""


# ---------------------------------------------------------------------------
# get_auth — env-var-driven
# ---------------------------------------------------------------------------


def _make_config(
    username_env: str = "JENKINS_USER",
    token_env: str = "JENKINS_TOKEN",  # noqa: S107
) -> JenkinsConfig:
    return JenkinsConfig(
        base_url="https://ci.example.com",
        auth=JenkinsAuthConfig(username_env=username_env, token_env=token_env),
        pipelines={"dummy": {"uri": "/job/dummy/build"}},
    )


def test_get_auth_returns_tuple_when_both_env_vars_set(monkeypatch):
    monkeypatch.setenv("JENKINS_USER", "alice")
    monkeypatch.setenv("JENKINS_TOKEN", "secret-token")
    result = get_auth(_make_config())
    assert result == ("alice", "secret-token")


def test_get_auth_returns_none_when_username_missing(monkeypatch):
    monkeypatch.delenv("JENKINS_USER", raising=False)
    monkeypatch.setenv("JENKINS_TOKEN", "secret-token")
    result = get_auth(_make_config())
    assert result is None


def test_get_auth_returns_none_when_token_missing(monkeypatch):
    monkeypatch.setenv("JENKINS_USER", "alice")
    monkeypatch.delenv("JENKINS_TOKEN", raising=False)
    result = get_auth(_make_config())
    assert result is None


def test_get_auth_returns_none_when_both_missing(monkeypatch):
    monkeypatch.delenv("JENKINS_USER", raising=False)
    monkeypatch.delenv("JENKINS_TOKEN", raising=False)
    result = get_auth(_make_config())
    assert result is None


def test_get_auth_uses_custom_env_var_names(monkeypatch):
    monkeypatch.setenv("MY_JENKINS_USER", "bob")
    monkeypatch.setenv("MY_JENKINS_TOKEN", "my-token")
    cfg = _make_config(username_env="MY_JENKINS_USER", token_env="MY_JENKINS_TOKEN")
    result = get_auth(cfg)
    assert result == ("bob", "my-token")
