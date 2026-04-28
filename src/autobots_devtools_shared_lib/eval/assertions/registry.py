# ABOUTME: Maps YAML assertion names to evaluator functions.
# ABOUTME: Supports built-in assertions and custom consumer-registered assertions.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.eval.models.result import AgentOutput, AssertionResult


class EvalFn(Protocol):
    """Protocol for assertion evaluator functions."""

    def __call__(self, agent_output: AgentOutput, config: Any) -> AssertionResult: ...


_REGISTRY: dict[str, EvalFn] = {}


def _register_builtins() -> None:
    """Lazily register built-in assertions on first access."""
    if _REGISTRY:
        return

    from autobots_devtools_shared_lib.eval.assertions.deterministic import (
        contains,
        exact_match,
        json_match,
        no_extra_tools,
        regex,
        schema_match,
        tool_called,
        tool_sequence,
        tools_unordered,
    )
    from autobots_devtools_shared_lib.eval.assertions.golden import golden_match
    from autobots_devtools_shared_lib.eval.assertions.llm_judge import (
        llm_judge,
        trajectory_quality,
    )
    from autobots_devtools_shared_lib.eval.assertions.written_file import written_file_matches

    _REGISTRY.update(
        cast(
            "dict[str, EvalFn]",
            {
                "contains": contains,
                "regex": regex,
                "exact_match": exact_match,
                "json_match": json_match,
                "response_matches_schema": schema_match,
                "tool_called": tool_called,
                "tool_sequence": tool_sequence,
                "no_extra_tools": no_extra_tools,
                "tools_unordered": tools_unordered,
                "llm_judge": llm_judge,
                "trajectory_quality": trajectory_quality,
                "golden_match": golden_match,
                "written_file_matches": written_file_matches,
            },
        )
    )


def register_assertion(name: str, fn: EvalFn) -> None:
    """Register a custom assertion evaluator."""
    _register_builtins()
    _REGISTRY[name] = fn


def resolve_assertion(name: str) -> EvalFn:
    """Look up an assertion evaluator by name. Raises KeyError if not found."""
    _register_builtins()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        msg = f"Unknown assertion '{name}'. Available: {available}"
        raise KeyError(msg)
    return _REGISTRY[name]
