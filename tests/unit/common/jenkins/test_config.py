# ABOUTME: Unit tests for Jenkins Pydantic configuration models.
# ABOUTME: Verifies parsing, defaults, validation errors, and per-pipeline overrides.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autobots_devtools_shared_lib.common.config.jenkins_config import (
    JenkinsAuthConfig,
    JenkinsConfig,
    JenkinsParameterConfig,
    JenkinsPollingConfig,
)

# --- Minimal valid input helpers ---

_MINIMAL_PIPELINE = {"uri": "/job/my-job/buildWithParameters"}

_MINIMAL_CONFIG = {
    "base_url": "https://ci.example.com",
    "pipelines": {"my_job": _MINIMAL_PIPELINE},
}


# --- JenkinsConfig: happy-path parsing ---


def test_minimal_config_parses():
    cfg = JenkinsConfig.model_validate(_MINIMAL_CONFIG)
    assert cfg.base_url == "https://ci.example.com"
    assert "my_job" in cfg.pipelines


def test_auth_defaults_applied_when_omitted():
    cfg = JenkinsConfig.model_validate(_MINIMAL_CONFIG)
    assert cfg.auth.username_env == "JENKINS_USERNAME"
    assert cfg.auth.token_env == "JENKINS_API_TOKEN"  # noqa: S105


def test_polling_defaults_applied_when_omitted():
    cfg = JenkinsConfig.model_validate(_MINIMAL_CONFIG)
    assert cfg.polling.wait_for_completion is True
    assert cfg.polling.poll_interval_seconds == 10
    assert cfg.polling.max_wait_seconds == 300
    assert cfg.polling.queue_max_retries == 5
    assert cfg.polling.queue_retry_delay_seconds == 2


def test_auth_custom_values_preserved():
    raw = {
        **_MINIMAL_CONFIG,
        "auth": {"username_env": "MY_USER", "token_env": "MY_TOKEN"},
    }
    cfg = JenkinsConfig.model_validate(raw)
    assert cfg.auth.username_env == "MY_USER"
    assert cfg.auth.token_env == "MY_TOKEN"  # noqa: S105


def test_global_polling_custom_values_preserved():
    raw = {
        **_MINIMAL_CONFIG,
        "polling": {
            "wait_for_completion": False,
            "poll_interval_seconds": 5,
            "max_wait_seconds": 60,
            "queue_max_retries": 3,
            "queue_retry_delay_seconds": 1,
        },
    }
    cfg = JenkinsConfig.model_validate(raw)
    assert cfg.polling.wait_for_completion is False
    assert cfg.polling.max_wait_seconds == 60


# --- JenkinsConfig: validation errors ---


def test_missing_base_url_raises():
    with pytest.raises(ValidationError):
        JenkinsConfig.model_validate({"pipelines": {"p": _MINIMAL_PIPELINE}})


def test_missing_pipelines_raises():
    with pytest.raises(ValidationError):
        JenkinsConfig.model_validate({"base_url": "https://ci.example.com"})


# --- JenkinsPipelineConfig ---


def test_pipeline_uri_preserved():
    cfg = JenkinsConfig.model_validate(_MINIMAL_CONFIG)
    assert cfg.pipelines["my_job"].uri == "/job/my-job/buildWithParameters"


def test_pipeline_description_defaults_to_empty():
    cfg = JenkinsConfig.model_validate(_MINIMAL_CONFIG)
    assert cfg.pipelines["my_job"].description == ""


def test_pipeline_missing_uri_raises():
    raw = {
        "base_url": "https://ci.example.com",
        "pipelines": {"bad": {"description": "no uri here"}},
    }
    with pytest.raises(ValidationError):
        JenkinsConfig.model_validate(raw)


def test_pipeline_polling_override_preserved():
    raw = {
        "base_url": "https://ci.example.com",
        "pipelines": {
            "fast_job": {
                "uri": "/job/fast/build",
                "polling": {"wait_for_completion": True, "max_wait_seconds": 60},
            }
        },
    }
    cfg = JenkinsConfig.model_validate(raw)
    assert cfg.pipelines["fast_job"].polling is not None
    assert cfg.pipelines["fast_job"].polling.max_wait_seconds == 60


def test_pipeline_without_polling_defaults_to_none():
    cfg = JenkinsConfig.model_validate(_MINIMAL_CONFIG)
    assert cfg.pipelines["my_job"].polling is None


def test_multiple_pipelines_all_parsed():
    raw = {
        "base_url": "https://ci.example.com",
        "pipelines": {
            "job_a": {"uri": "/job/a/build"},
            "job_b": {"uri": "/job/b/build"},
            "job_c": {"uri": "/job/c/build"},
        },
    }
    cfg = JenkinsConfig.model_validate(raw)
    assert set(cfg.pipelines.keys()) == {"job_a", "job_b", "job_c"}


# --- JenkinsParameterConfig ---


def test_parameter_required_defaults_to_true():
    p = JenkinsParameterConfig(type="string", description="some param")
    assert p.required is True


def test_parameter_required_false_preserved():
    p = JenkinsParameterConfig(type="boolean", description="optional flag", required=False)
    assert p.required is False


def test_parameter_type_defaults_to_string():
    p = JenkinsParameterConfig(description="a param")
    assert p.type == "string"


def test_parameter_description_defaults_to_empty():
    p = JenkinsParameterConfig()
    assert p.description == ""


# --- JenkinsPollingConfig ---


def test_polling_wait_for_completion_false():
    p = JenkinsPollingConfig(wait_for_completion=False)
    assert p.wait_for_completion is False


def test_polling_custom_interval():
    p = JenkinsPollingConfig(poll_interval_seconds=30)
    assert p.poll_interval_seconds == 30


# --- JenkinsAuthConfig ---


def test_auth_defaults():
    auth = JenkinsAuthConfig()
    assert auth.username_env == "JENKINS_USERNAME"
    assert auth.token_env == "JENKINS_API_TOKEN"  # noqa: S105


def test_auth_custom():
    auth = JenkinsAuthConfig(username_env="U", token_env="T")
    assert auth.username_env == "U"
    assert auth.token_env == "T"  # noqa: S105
