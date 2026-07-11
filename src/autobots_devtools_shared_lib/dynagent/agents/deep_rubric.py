# ABOUTME: Builds deepagents RubricMiddleware instances from rubric: roster config.
# ABOUTME: Grader model/prompt/tools reuse the profile, prompt-file, and registry plumbing.

from typing import Any

from deepagents import RubricMiddleware

from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import load_prompt
from autobots_devtools_shared_lib.dynagent.llm.model_resolution import resolve_model_ref
from autobots_devtools_shared_lib.dynagent.tools.tool_registry import get_all_tools


def _resolve_grader_tools(agent_name: str, tool_names: list[str]) -> list[Any]:
    tool_by_name = {t.name: t for t in get_all_tools()}
    resolved: list[Any] = []
    for tool_name in tool_names:
        if tool_name not in tool_by_name:
            msg = (
                f"Agent '{agent_name}': rubric grader tool '{tool_name}' is not registered. "
                f"Available tools: {sorted(tool_by_name)}"
            )
            raise ValueError(msg)
        resolved.append(tool_by_name[tool_name])
    return resolved


def build_rubric_middleware(
    meta: Any, agent_name: str, agent_model: Any
) -> RubricMiddleware | None:
    """Return a configured RubricMiddleware, or None when the agent has no rubric: block.

    The middleware is a no-op at runtime unless the caller passes a `rubric`
    string in invocation state, so appending it when configured is safe.
    """
    rubric = meta.rubric_map.get(agent_name)
    if rubric is None:
        return None

    model_ref = rubric.get("model")
    model = resolve_model_ref(model_ref, meta.model_profiles) if model_ref else agent_model

    prompt_name = rubric.get("prompt")
    system_prompt = load_prompt(prompt_name) if prompt_name else None

    tools = _resolve_grader_tools(agent_name, rubric.get("tools") or [])

    return RubricMiddleware(
        model=model,
        system_prompt=system_prompt,
        tools=tools or None,
        max_iterations=rubric.get("max_iterations", 3),
    )
