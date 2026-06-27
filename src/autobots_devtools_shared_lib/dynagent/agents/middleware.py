# ABOUTME: Middleware that injects agent-specific prompts and tools on every LLM call.
# ABOUTME: Reads current agent_name from state and overrides via AgentMeta.

import json
from collections import defaultdict
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.messages import SystemMessage

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta

logger = get_logger(__name__)


@wrap_model_call  # type: ignore[arg-type]
async def inject_agent_async(
    request: ModelRequest,
    handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
) -> ModelResponse:
    """Belt-and-suspenders: inject prompt + tools from AgentMeta on every model call."""
    meta = AgentMeta.instance()

    agent_name = request.state.get("agent_name", meta.default_agent or "coordinator")
    logger.info(f"inject_agent: active agent = {agent_name}")

    # Format prompt safely — missing placeholders become empty strings
    raw_prompt = meta.prompt_map.get(agent_name, "")

    # Inject resolved input schemas (if any) as JSON strings using their schema keys.
    input_schemas = meta.input_schema_map.get(agent_name, {})
    input_directives_map = {
        schema_key: json.dumps(schema, indent=2, sort_keys=True)
        for schema_key, schema in input_schemas.items()
    }

    input_directives = {"input_schemas": input_directives_map}
    output_directives = {"output_schema": meta.output_schema_map.get(agent_name, {}) or {}}

    # request.state values take precedence on key collision, consistent with previous behavior.
    combined_values = {**input_directives, **output_directives, **request.state}
    format_values = defaultdict(str, **combined_values)
    system_prompt = raw_prompt.format_map(format_values)

    tools = meta.tool_map.get(agent_name, [])

    messages = [m for m in request.messages if not isinstance(m, SystemMessage)]

    request = request.override(
        system_message=SystemMessage(content=system_prompt),
        tools=tools,
        messages=messages,
    )

    return await handler(request)


@wrap_model_call  # type: ignore[arg-type]
def inject_agent_sync(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Belt-and-suspenders: inject prompt + tools from AgentMeta on every model call."""
    meta = AgentMeta.instance()

    agent_name = request.state.get("agent_name", meta.default_agent or "coordinator")
    logger.info(f"inject_agent: active agent = {agent_name}")

    # Format prompt safely — missing placeholders become empty strings
    raw_prompt = meta.prompt_map.get(agent_name, "")

    # Inject resolved input schemas (if any) as JSON strings using their schema keys.
    input_schemas = meta.input_schema_map.get(agent_name, {})
    input_directives_map = {
        schema_key: json.dumps(schema, indent=2, sort_keys=True)
        for schema_key, schema in input_schemas.items()
    }

    input_directives = {"input_schemas": input_directives_map}
    output_directives = {"output_schema": meta.output_schema_map.get(agent_name, {}) or {}}

    # request.state values take precedence on key collision, consistent with previous behavior.
    combined_values = {**input_directives, **output_directives, **request.state}
    format_values = defaultdict(str, **combined_values)
    system_prompt = raw_prompt.format_map(format_values)

    tools = meta.tool_map.get(agent_name, [])

    messages = [m for m in request.messages if not isinstance(m, SystemMessage)]

    request = request.override(
        system_message=SystemMessage(content=system_prompt),
        tools=tools,
        messages=messages,
    )

    return handler(request)
