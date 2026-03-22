# ABOUTME: Tests for the assertion registry.
# ABOUTME: Validates lookup, registration of custom assertions, and unknown assertion error.

import pytest

from autobots_devtools_shared_lib.eval.assertions.registry import (
    register_assertion,
    resolve_assertion,
)
from autobots_devtools_shared_lib.eval.models.result import AgentOutput, AssertionResult


def test_resolve_builtin_contains():
    fn = resolve_assertion("contains")
    assert callable(fn)


def test_resolve_builtin_tool_called():
    fn = resolve_assertion("tool_called")
    assert callable(fn)


def test_resolve_unknown_raises():
    with pytest.raises(KeyError, match="no_such_assertion"):
        resolve_assertion("no_such_assertion")


def test_register_custom_assertion():
    def my_custom(agent_output: AgentOutput, config: object) -> AssertionResult:
        return AssertionResult(passed=True, name="my_custom", detail="ok")

    register_assertion("my_custom", my_custom)
    fn = resolve_assertion("my_custom")
    assert fn is my_custom


def test_resolve_all_builtins():
    """All spec-defined assertion names are resolvable."""
    builtins = [
        "contains",
        "regex",
        "exact_match",
        "json_match",
        "response_matches_schema",
        "tool_called",
        "tool_sequence",
        "no_extra_tools",
        "tools_unordered",
        "llm_judge",
        "trajectory_quality",
    ]
    for name in builtins:
        fn = resolve_assertion(name)
        assert callable(fn), f"{name} not callable"
