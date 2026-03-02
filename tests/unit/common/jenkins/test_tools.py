# ABOUTME: Unit tests for Jenkins LangChain tool creation and auto-registration.
# ABOUTME: Verifies tool name suffix, description, args-schema shape, and idempotency.

from __future__ import annotations

import textwrap
from typing import get_args, get_origin

import pytest

from autobots_devtools_shared_lib.common.jenkins.config import (
    JenkinsConfig,
    JenkinsParameterConfig,
    JenkinsPipelineConfig,
)
from autobots_devtools_shared_lib.common.tools.jenkins_pipeline_tools import (
    create_jenkins_tools,
    register_pipeline_tools,
)
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import (
    _reset_usecase_tools,
    get_jenkins_usecase_tools,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_MINIMAL_YAML = textwrap.dedent("""\
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
""")


@pytest.fixture
def cfg() -> JenkinsConfig:
    """In-memory JenkinsConfig with one pipeline and two params (1 required, 1 optional)."""
    return JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={
            "deploy_app": JenkinsPipelineConfig(
                uri="/job/deploy-app/buildWithParameters",
                description="Deploy the application",
                parameters={
                    "ENV": JenkinsParameterConfig(
                        type="string", description="Target environment", required=True
                    ),
                    "SKIP_TESTS": JenkinsParameterConfig(
                        type="boolean", description="Skip tests flag", required=False
                    ),
                },
            )
        },
    )


@pytest.fixture(autouse=True)
def reset_state(monkeypatch, tmp_path):
    """Reset all registration state and point config dir at tmp_path before each test."""
    _reset_usecase_tools()
    monkeypatch.setattr(
        "autobots_devtools_shared_lib.dynagent.agents.agent_config_utils.get_config_dir",
        lambda: tmp_path,
    )
    yield
    _reset_usecase_tools()


# ---------------------------------------------------------------------------
# create_jenkins_tools — tool creation shape
# ---------------------------------------------------------------------------


def test_create_tools_returns_one_tool_per_pipeline(cfg):
    tools = create_jenkins_tools(cfg)
    assert len(tools) == 1


def test_tool_name_has_underscore_tool_suffix(cfg):
    tools = create_jenkins_tools(cfg)
    assert tools[0].name == "deploy_app_tool"


def test_tool_description_matches_pipeline_description(cfg):
    tools = create_jenkins_tools(cfg)
    assert tools[0].description == "Deploy the application"


def test_tool_fallback_description_when_empty():
    cfg = JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={
            "my_job": JenkinsPipelineConfig(
                uri="/job/my-job/build",
                description="",  # empty → fallback
            )
        },
    )
    tools = create_jenkins_tools(cfg)
    assert "my-job" in tools[0].description or "/job/" in tools[0].description


def test_tool_is_invocable(cfg):
    tools = create_jenkins_tools(cfg)
    assert hasattr(tools[0], "invoke")


def test_multiple_pipelines_produce_multiple_tools():
    cfg = JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={
            "job_a": JenkinsPipelineConfig(uri="/job/a/build"),
            "job_b": JenkinsPipelineConfig(uri="/job/b/build"),
            "job_c": JenkinsPipelineConfig(uri="/job/c/build"),
        },
    )
    tools = create_jenkins_tools(cfg)
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"job_a_tool", "job_b_tool", "job_c_tool"}


# ---------------------------------------------------------------------------
# args_schema shape — required and optional parameters
# ---------------------------------------------------------------------------


def test_args_schema_has_required_field(cfg):
    tools = create_jenkins_tools(cfg)
    schema = tools[0].args_schema
    assert schema is not None
    fields = schema.model_fields
    assert "ENV" in fields


def test_required_field_is_plain_str(cfg):
    tools = create_jenkins_tools(cfg)
    schema = tools[0].args_schema
    env_field = schema.model_fields["ENV"]
    # Required field has no default
    assert env_field.default is None or env_field.is_required()
    # Annotation should be str (not str | None)
    assert env_field.annotation is str


def test_args_schema_has_optional_field(cfg):
    tools = create_jenkins_tools(cfg)
    schema = tools[0].args_schema
    assert "SKIP_TESTS" in schema.model_fields


def test_optional_field_is_bool_or_none(cfg):
    tools = create_jenkins_tools(cfg)
    schema = tools[0].args_schema
    skip_field = schema.model_fields["SKIP_TESTS"]
    # Annotation should be bool | None
    annotation = skip_field.annotation
    origin = get_origin(annotation)
    args = get_args(annotation)
    # Union type containing bool and NoneType
    assert origin is not None, "Expected a Union/Optional type for optional param"
    assert bool in args
    assert type(None) in args


def test_optional_field_has_none_default(cfg):
    tools = create_jenkins_tools(cfg)
    schema = tools[0].args_schema
    skip_field = schema.model_fields["SKIP_TESTS"]
    assert skip_field.default is None


def test_pipeline_with_no_params_produces_empty_schema():
    cfg = JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={"no_params": JenkinsPipelineConfig(uri="/job/np/build")},
    )
    tools = create_jenkins_tools(cfg)
    assert tools[0].args_schema is not None
    assert len(tools[0].args_schema.model_fields) == 0


# ---------------------------------------------------------------------------
# Parameter type mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_str, expected_py_type",
    [
        ("string", str),
        ("str", str),
        ("boolean", bool),
        ("bool", bool),
        ("integer", int),
        ("int", int),
        ("float", float),
        ("number", float),
    ],
)
def test_parameter_type_mapping(type_str, expected_py_type):
    cfg = JenkinsConfig(
        base_url="https://ci.example.com",
        pipelines={
            "typed_job": JenkinsPipelineConfig(
                uri="/job/typed/build",
                parameters={
                    "PARAM": JenkinsParameterConfig(
                        type=type_str, description="typed param", required=True
                    )
                },
            )
        },
    )
    tools = create_jenkins_tools(cfg)
    field = tools[0].args_schema.model_fields["PARAM"]
    assert field.annotation is expected_py_type


# ---------------------------------------------------------------------------
# register_pipeline_tools — idempotency and no-op behaviour
# ---------------------------------------------------------------------------


def test_register_pipeline_tools_noop_when_no_yaml(tmp_path):
    """No jenkins.yaml → returns empty list."""
    result = register_pipeline_tools()
    assert result == []


def test_register_pipeline_tools_returns_pipeline_tools(tmp_path):
    """jenkins.yaml present → pipeline tools in returned list."""
    (tmp_path / "jenkins.yaml").write_text(_MINIMAL_YAML)
    tools = register_pipeline_tools()
    names = {t.name for t in tools}
    assert "deploy_app_tool" in names


def test_register_pipeline_tools_includes_builtins_when_yaml_present(tmp_path):
    """jenkins.yaml present → builtin observability tools included alongside pipeline tools."""
    (tmp_path / "jenkins.yaml").write_text(_MINIMAL_YAML)
    tools = register_pipeline_tools()
    names = {t.name for t in tools}
    assert "get_jenkins_build_status" in names
    assert "get_jenkins_console_log" in names


def test_register_pipeline_tools_builtins_absent_when_no_yaml(tmp_path):
    """No jenkins.yaml → builtin observability tools NOT returned."""
    tools = register_pipeline_tools()
    names = {t.name for t in tools}
    assert "get_jenkins_build_status" not in names
    assert "get_jenkins_console_log" not in names


def test_get_jenkins_usecase_tools_caches_result(tmp_path):
    """Cache in tool_registry prevents repeated disk reads — idempotency owner."""
    (tmp_path / "jenkins.yaml").write_text(_MINIMAL_YAML)
    first = get_jenkins_usecase_tools()
    second = get_jenkins_usecase_tools()
    assert first is second  # same cached list object, no re-read


def test_get_jenkins_usecase_tools_no_duplicates(tmp_path):
    """Calling get_jenkins_usecase_tools() multiple times never duplicates tools."""
    (tmp_path / "jenkins.yaml").write_text(_MINIMAL_YAML)
    get_jenkins_usecase_tools()
    get_jenkins_usecase_tools()
    names = [t.name for t in get_jenkins_usecase_tools()]
    assert names.count("deploy_app_tool") == 1
