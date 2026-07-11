# ABOUTME: Unit tests for config-driven RubricMiddleware construction and factory wiring.
# ABOUTME: Covers grader model/prompt/tools resolution, ordering, and rubric state passthrough.

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from deepagents import RubricMiddleware

import autobots_devtools_shared_lib.dynagent.agents.deep_rubric as dr
from autobots_devtools_shared_lib.dynagent.agents.deep_rubric import build_rubric_middleware


def _meta(rubric=None, profiles=None):
    return SimpleNamespace(
        rubric_map={"assistant": rubric},
        model_profiles=profiles or {},
    )


def test_no_rubric_returns_none():
    assert build_rubric_middleware(_meta(None), "assistant", "AGENT_MODEL") is None


def test_grader_defaults_to_agent_model():
    mw = build_rubric_middleware(_meta({}), "assistant", "AGENT_MODEL")
    assert isinstance(mw, RubricMiddleware)
    assert mw._model == "AGENT_MODEL"
    assert mw.max_iterations == 3


def test_grader_model_resolved_from_profile():
    profiles = {"cheap-docs": {"provider": "anthropic", "name": "claude-haiku-4-5"}}
    with patch.object(dr, "resolve_model_ref", return_value="GRADER") as resolve:
        mw = build_rubric_middleware(
            _meta({"model": "cheap-docs"}, profiles), "assistant", "AGENT_MODEL"
        )
    resolve.assert_called_once_with("cheap-docs", profiles)
    assert mw._model == "GRADER"


def test_grader_prompt_loaded_from_prompt_file():
    with patch.object(dr, "load_prompt", return_value="Grade strictly.") as load:
        mw = build_rubric_middleware(_meta({"prompt": "rubric-grader"}), "assistant", "AGENT_MODEL")
    load.assert_called_once_with("rubric-grader")
    assert mw._system_prompt == "Grade strictly."


def test_grader_tools_resolved_from_registry():
    fake_tool = SimpleNamespace(name="run_test_suite")
    with patch.object(dr, "get_all_tools", return_value=[fake_tool]):
        mw = build_rubric_middleware(
            _meta({"tools": ["run_test_suite"]}), "assistant", "AGENT_MODEL"
        )
    assert mw._tools == [fake_tool]


def test_unknown_grader_tool_fails_fast():
    with (
        patch.object(dr, "get_all_tools", return_value=[]),
        pytest.raises(ValueError, match="run_test_suite"),
    ):
        build_rubric_middleware(_meta({"tools": ["run_test_suite"]}), "assistant", "AGENT_MODEL")


def test_max_iterations_forwarded():
    mw = build_rubric_middleware(_meta({"max_iterations": 5}), "assistant", "AGENT_MODEL")
    assert mw.max_iterations == 5
