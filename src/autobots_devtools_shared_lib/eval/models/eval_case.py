# ABOUTME: Pydantic models for YAML eval case definitions.
# ABOUTME: Parses eval YAML into typed, validated EvalCase objects.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator


class Assertion(BaseModel):
    """Single assertion parsed from YAML.

    YAML format is {assertion_name: config_value}, e.g.:
      - contains: "hello"
      - tool_called: "my_tool"
      - llm_judge: {criteria: "...", threshold: 0.8}
      - tool_sequence: [{tool: "a"}, {tool: "b"}]
    """

    name: str
    config: Any

    @model_validator(mode="before")
    @classmethod
    def parse_yaml_dict(cls, data: Any) -> dict[str, Any]:
        if isinstance(data, dict) and "name" not in data:
            if len(data) != 1:
                msg = f"Assertion must have exactly one key, got {list(data.keys())}"
                raise ValueError(msg)
            name, config = next(iter(data.items()))
            return {"name": name, "config": config}
        return data


class CostConfig(BaseModel):
    """Cost tracking configuration."""

    track: bool = False


class RetryConfig(BaseModel):
    """Retry configuration for flaky assertions."""

    count: int = 0
    only_for: list[str] = []


class Turn(BaseModel):
    """Single conversation turn: user message + assertions on agent response."""

    user: str
    assertions: list[Assertion] = []


class EvalCase(BaseModel):
    """Top-level eval case parsed from YAML."""

    name: str
    agent: str
    mode: Literal["linear", "goal"]
    tags: list[str] = []
    state: dict[str, Any] = {}
    turns: list[Turn] | None = None
    retry: RetryConfig = RetryConfig()
    cost: CostConfig = CostConfig()

    @field_validator("turns")
    @classmethod
    def linear_requires_turns(cls, v: list[Turn] | None, info: Any) -> list[Turn] | None:
        if info.data.get("mode") == "linear" and (v is None or len(v) == 0):
            msg = "Linear mode requires at least one turn"
            raise ValueError(msg)
        return v
