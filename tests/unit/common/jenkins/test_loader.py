# ABOUTME: Unit tests for jenkins.yaml loader.
# ABOUTME: Verifies absent-file no-op, valid YAML parsing, and error propagation.

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
import yaml
from pydantic import ValidationError

from autobots_devtools_shared_lib.common.jenkins.loader import load_jenkins_config

# --- Fixture: point get_config_dir at a temp directory for each test ---

_VALID_YAML = textwrap.dedent("""\
    jenkins_config:
      base_url: "https://ci.example.com"
      pipelines:
        deploy_app:
          uri: "/job/deploy-app/buildWithParameters"
          description: "Deploy the application"
          parameters:
            ENV:
              type: string
              description: "Target environment"
              required: true
            SKIP_TESTS:
              type: boolean
              description: "Skip tests flag"
              required: false
        run_tests:
          uri: "/job/run-tests/build"
          description: "Run the test suite"
""")


@pytest.fixture(autouse=True)
def patch_config_dir(monkeypatch, tmp_path):
    """Redirect get_config_dir to a fresh tmp directory for every test.

    loader.py does a lazy import of get_config_dir inside the function body,
    so we must patch it on the source module (agent_config_utils), not on loader.
    """
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: tmp_path,
    )


def _write_jenkins_yaml(tmp_path: Path, content: str) -> None:
    (tmp_path / "jenkins.yaml").write_text(content)


# --- Absent file ---


def test_returns_none_when_no_jenkins_yaml(tmp_path):
    result = load_jenkins_config()
    assert result is None


# --- Valid YAML ---


def test_loads_valid_yaml_returns_config(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None


def test_loaded_config_has_correct_pipeline_count(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    assert len(cfg.pipelines) == 2


def test_loaded_config_pipeline_names(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    assert set(cfg.pipelines.keys()) == {"deploy_app", "run_tests"}


def test_loaded_config_base_url(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    assert cfg.base_url == "https://ci.example.com"


def test_loaded_pipeline_uri_preserved(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    assert cfg.pipelines["deploy_app"].uri == "/job/deploy-app/buildWithParameters"


def test_loaded_pipeline_description_preserved(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    assert cfg.pipelines["deploy_app"].description == "Deploy the application"


def test_loaded_pipeline_required_parameter(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    env_param = cfg.pipelines["deploy_app"].parameters["ENV"]
    assert env_param.required is True
    assert env_param.type == "string"


def test_loaded_pipeline_optional_parameter(tmp_path):
    _write_jenkins_yaml(tmp_path, _VALID_YAML)
    cfg = load_jenkins_config()
    assert cfg is not None
    skip_param = cfg.pipelines["deploy_app"].parameters["SKIP_TESTS"]
    assert skip_param.required is False
    assert skip_param.type == "boolean"


# --- Error propagation ---


def test_invalid_yaml_raises_yaml_error(tmp_path):
    _write_jenkins_yaml(tmp_path, "jenkins_config: [\nbad yaml: }")
    with pytest.raises(yaml.YAMLError):
        load_jenkins_config()


def test_valid_yaml_missing_uri_raises_validation_error(tmp_path):
    bad_yaml = textwrap.dedent("""\
        jenkins_config:
          base_url: "https://ci.example.com"
          pipelines:
            broken_pipeline:
              description: "no uri here"
    """)
    _write_jenkins_yaml(tmp_path, bad_yaml)
    with pytest.raises(ValidationError):
        load_jenkins_config()


def test_valid_yaml_missing_base_url_raises_validation_error(tmp_path):
    bad_yaml = textwrap.dedent("""\
        jenkins_config:
          pipelines:
            my_job:
              uri: "/job/my-job/build"
    """)
    _write_jenkins_yaml(tmp_path, bad_yaml)
    with pytest.raises(ValidationError):
        load_jenkins_config()
