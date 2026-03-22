# ABOUTME: Deterministic assertion functions wrapping OpenEvals and built-in checks.
# ABOUTME: Each function takes AgentOutput + config and returns AssertionResult.

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema as js

from autobots_devtools_shared_lib.eval.models.result import AgentOutput, AssertionResult


def _last_ai_content(agent_output: AgentOutput) -> str:
    """Extract text content from the last AI message."""
    for msg in reversed(agent_output.messages):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            return str(msg.content)
    return ""


def _all_tool_names(agent_output: AgentOutput) -> list[str]:
    """Extract all tool names called across all messages."""
    names: list[str] = []
    for msg in agent_output.messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    names.append(tc.get("name", ""))
                elif hasattr(tc, "name"):
                    names.append(tc.name)
    return names


def contains(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check if agent response contains a substring (case-insensitive)."""
    text = _last_ai_content(agent_output).lower()
    target = str(config).lower()
    found = target in text
    return AssertionResult(
        passed=found,
        name=f"contains:{config}",
        detail=f"{'Found' if found else 'Not found'} in response",
    )


def regex(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check if agent response matches a regex pattern."""
    text = _last_ai_content(agent_output)
    pattern = str(config)
    match = bool(re.search(pattern, text))
    return AssertionResult(
        passed=match,
        name=f"regex:{pattern}",
        detail=f"{'Matched' if match else 'No match'} for pattern",
    )


def exact_match(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check if agent response exactly matches expected string."""
    text = _last_ai_content(agent_output)
    expected = str(config)
    passed = text.strip() == expected.strip()
    return AssertionResult(
        passed=passed,
        name="exact_match",
        detail=f"Expected: {expected[:100]}",
    )


def json_match(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check if agent response JSON matches expected JSON."""
    text = _last_ai_content(agent_output)
    try:
        actual = json.loads(text)
        expected = config if isinstance(config, dict) else json.loads(str(config))
        passed = actual == expected
        return AssertionResult(
            passed=passed,
            name="json_match",
            detail="JSON matches" if passed else "JSON does not match",
        )
    except (json.JSONDecodeError, TypeError) as e:
        return AssertionResult(passed=False, name="json_match", detail=f"Parse error: {e}")


def schema_match(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Validate agent response JSON against a JSON schema file."""
    text = _last_ai_content(agent_output)
    schema_path = Path(str(config))
    try:
        schema = json.loads(schema_path.read_text())
        data = json.loads(text)
        js.validate(instance=data, schema=schema)
        return AssertionResult(passed=True, name="response_matches_schema", detail="Valid")
    except js.ValidationError as e:
        return AssertionResult(
            passed=False,
            name="response_matches_schema",
            detail=f"Schema validation failed: {e.message}",
        )
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        return AssertionResult(
            passed=False,
            name="response_matches_schema",
            detail=f"Error: {e}",
        )


def tool_called(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check if a specific tool was called during the conversation."""
    target = str(config)
    called = _all_tool_names(agent_output)
    found = target in called
    return AssertionResult(
        passed=found,
        name=f"tool_called:{target}",
        detail=f"Tools called: {called}" if not found else "Found",
    )


def tool_sequence(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check if tools were called in a specific order."""
    if not isinstance(config, list):
        return AssertionResult(passed=False, name="tool_sequence", detail="Config must be a list")

    expected_names = [step["tool"] for step in config if isinstance(step, dict)]
    called = _all_tool_names(agent_output)

    # Check subsequence match (in order, not necessarily contiguous)
    idx = 0
    for name in called:
        if idx < len(expected_names) and name == expected_names[idx]:
            idx += 1
    passed = idx == len(expected_names)

    return AssertionResult(
        passed=passed,
        name="tool_sequence",
        detail=f"Expected: {expected_names}, Called: {called}",
    )


def no_extra_tools(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check that no tools beyond the allowed set were called."""
    allowed = set(config) if isinstance(config, list) else {str(config)}
    called = set(_all_tool_names(agent_output))
    extra = called - allowed
    passed = len(extra) == 0
    return AssertionResult(
        passed=passed,
        name="no_extra_tools",
        detail=f"Extra tools: {extra}" if extra else "No extra tools",
    )


def tools_unordered(agent_output: AgentOutput, config: Any) -> AssertionResult:
    """Check that all expected tools were called (order doesn't matter)."""
    expected = set(config) if isinstance(config, list) else {str(config)}
    called = set(_all_tool_names(agent_output))
    missing = expected - called
    passed = len(missing) == 0
    return AssertionResult(
        passed=passed,
        name="tools_unordered",
        detail=f"Missing: {missing}" if missing else "All tools called",
    )
