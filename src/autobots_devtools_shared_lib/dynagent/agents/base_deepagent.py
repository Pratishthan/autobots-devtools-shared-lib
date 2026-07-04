# ABOUTME: Factory for the dynagent deep-agent engine.
# ABOUTME: Wraps deepagents' create_deep_agent, mirroring create_base_agent's role.

import json
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from deepagents import DeepAgentState, SubAgent, create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from autobots_devtools_shared_lib.common.observability import get_agent_logger
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.deep_backend import resolve_backend
from autobots_devtools_shared_lib.dynagent.llm.model_resolution import resolve_agent_model
from autobots_devtools_shared_lib.dynagent.middleware.tool_resilience import (
    ToolResilienceMiddleware,
)
from autobots_devtools_shared_lib.dynagent.models.deep_state import DynaDeepAgent

logger = get_agent_logger(__name__)


def _resolve_system_prompt(
    meta: AgentMeta, agent_name: str, prompt_values: dict[str, Any] | None
) -> str:
    """Build the static system prompt: raw prompt + one-time format_map substitution.

    Retains dynagent's placeholder templating (e.g. {language} -> java) but resolves
    it once at build time, since the deep engine uses a static system_prompt.
    """
    raw_prompt = meta.prompt_map.get(agent_name, "")
    input_schemas = meta.input_schema_map.get(agent_name, {})
    input_directives = {
        schema_key: json.dumps(schema, indent=2, sort_keys=True)
        for schema_key, schema in input_schemas.items()
    }
    values = {
        "input_schemas": input_directives,
        "output_schema": meta.output_schema_map.get(agent_name, {}) or {},
        **(prompt_values or {}),
    }
    return raw_prompt.format_map(defaultdict(str, values))


def create_base_deepagent(
    checkpointer: Any = None,
    initial_agent_name: str | None = None,
    state_schema: type[DeepAgentState] = DynaDeepAgent,
    prompt_values: dict[str, Any] | None = None,
    subagents: Sequence[SubAgent] | None = None,
    backend: Any = None,
) -> CompiledStateGraph:
    """Create the dynagent deep-agent (deepagents-backed) engine.

    Mirrors create_base_agent but delegates the agent loop to deepagents'
    create_deep_agent, which supplies planning, virtual filesystem, sub-agents,
    summarization, and prompt caching. The deep engine deliberately does NOT
    attach inject_agent or our SummarizationMiddleware.

    Args:
        checkpointer: LangGraph checkpointer. Defaults to InMemorySaver.
        initial_agent_name: Roster agent to run as the main agent. Defaults to
            the config's default agent.
        state_schema: Deep-agent state schema. Defaults to DynaDeepAgent.
        prompt_values: Placeholder substitution values for the system prompt.
        subagents: Optional deepagents subagents (phase-2 roster mapping hook).
        backend: Live backend instance/factory override; wins over the YAML
            `default_backend`.

    Returns:
        A compiled deep-agent graph.
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    meta = AgentMeta.instance()

    if initial_agent_name is None:
        initial_agent_name = get_default_agent()
    agent_name = initial_agent_name or "assistant"
    logger.info(f"create_base_deepagent: main agent = {agent_name}")

    system_prompt = _resolve_system_prompt(meta, agent_name, prompt_values)
    tools = meta.tool_map.get(agent_name, [])

    return create_deep_agent(
        model=resolve_agent_model(meta, agent_name),
        tools=tools,
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
        name=agent_name,
        skills=meta.skills_map.get(agent_name) or None,
        memory=meta.memory_map.get(agent_name) or None,
        backend=resolve_backend(meta.backend_config, override=backend),
        subagents=list(subagents) if subagents else None,
        middleware=[ToolResilienceMiddleware()],
    )
