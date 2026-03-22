# ABOUTME: Tests for eval case Pydantic models.
# ABOUTME: Validates YAML-shaped dicts parse correctly into EvalCase models.
from __future__ import annotations

import pytest
from pydantic import ValidationError

from autobots_devtools_shared_lib.eval.models.eval_case import (
    Assertion,
    CostConfig,
    EvalCase,
    RetryConfig,
)


def test_minimal_linear_eval_case():
    """Minimal linear eval case with one turn and one assertion."""
    data = {
        "name": "test eval",
        "agent": "coordinator",
        "mode": "linear",
        "tags": ["smoke"],
        "state": {"user_name": "test"},
        "turns": [
            {
                "user": "Hello",
                "assertions": [{"contains": "hi"}],
            }
        ],
        "cost": {"track": False},
    }
    case = EvalCase.model_validate(data)
    assert case.name == "test eval"
    assert case.mode == "linear"
    assert len(case.turns) == 1
    assert len(case.turns[0].assertions) == 1


def test_linear_eval_case_with_multiple_assertions():
    """Linear case with tool_called, contains, and response_matches_schema."""
    data = {
        "name": "multi-assertion",
        "agent": "model-list-extractor",
        "mode": "linear",
        "tags": ["nurture"],
        "state": {"user_name": "test", "repo_name": "fbp-core"},
        "turns": [
            {
                "user": "Extract models",
                "assertions": [
                    {"tool_called": "mer_read_file_tool"},
                    {"contains": "Party"},
                    {"response_matches_schema": "schemas/model_list.json"},
                ],
            }
        ],
        "cost": {"track": True},
    }
    case = EvalCase.model_validate(data)
    assert len(case.turns[0].assertions) == 3
    assert case.turns[0].assertions[0].name == "tool_called"
    assert case.turns[0].assertions[0].config == "mer_read_file_tool"


def test_assertion_parsing_simple_string():
    """Assertion with string value like contains: 'hello'."""
    a = Assertion.model_validate({"contains": "hello"})
    assert a.name == "contains"
    assert a.config == "hello"


def test_assertion_parsing_dict_value():
    """Assertion with dict value like llm_judge: {criteria: ..., threshold: ...}."""
    a = Assertion.model_validate({"llm_judge": {"criteria": "Is it correct?", "threshold": 0.8}})
    assert a.name == "llm_judge"
    assert a.config["criteria"] == "Is it correct?"
    assert a.config["threshold"] == 0.8


def test_assertion_parsing_list_value():
    """Assertion with list value like tool_sequence: [...]."""
    a = Assertion.model_validate(
        {
            "tool_sequence": [
                {"tool": "set_context_tool"},
                {"tool": "mer_read_file_tool"},
            ]
        }
    )
    assert a.name == "tool_sequence"
    assert len(a.config) == 2


def test_cost_config_defaults():
    """CostConfig has sensible defaults."""
    c = CostConfig.model_validate({})
    assert c.track is False


def test_retry_config_defaults():
    """RetryConfig has sensible defaults."""
    r = RetryConfig.model_validate({})
    assert r.count == 0
    assert r.only_for == []


def test_invalid_mode_rejected():
    """Mode must be 'linear' or 'goal'."""
    with pytest.raises(ValidationError):
        EvalCase.model_validate(
            {
                "name": "bad",
                "agent": "x",
                "mode": "invalid",
                "tags": [],
                "state": {},
                "turns": [],
                "cost": {},
            }
        )


def test_linear_requires_turns():
    """Linear mode must have at least one turn."""
    with pytest.raises(ValidationError):
        EvalCase.model_validate(
            {
                "name": "bad",
                "agent": "x",
                "mode": "linear",
                "tags": [],
                "state": {},
                "turns": [],
                "cost": {},
            }
        )


def test_assertion_on_judge_error_default():
    """on_judge_error defaults to 'warn' when not specified."""
    a = Assertion.model_validate({"llm_judge": {"criteria": "Is it good?", "threshold": 0.8}})
    assert a.on_judge_error == "warn"


def test_assertion_on_judge_error_explicit():
    """on_judge_error can be set to 'fail'."""
    a = Assertion.model_validate(
        {"llm_judge": {"criteria": "Is it good?", "threshold": 0.8, "on_judge_error": "fail"}}
    )
    assert a.on_judge_error == "fail"


def test_assertion_on_judge_error_invalid():
    """on_judge_error rejects invalid values."""
    with pytest.raises(ValidationError):
        Assertion.model_validate(
            {"llm_judge": {"criteria": "Is it good?", "on_judge_error": "ignore"}}
        )
