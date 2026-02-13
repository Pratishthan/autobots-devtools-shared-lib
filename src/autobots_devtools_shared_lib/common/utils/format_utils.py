import json

from langchain_core.messages import AnyMessage

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.llm.llm import lm
from autobots_devtools_shared_lib.dynagent.services.structured_converter import (
    StructuredOutputConverter,
)

logger = get_logger(__name__)


def output_format_converter(agent_name: str, messages: list[AnyMessage]) -> str:
    """Convert conversation history to structured output.

    Uses the current agent's schema for extraction.

    Args:
        agent_name: Name of the current agent (used to find schema).
        messages: Full conversation history as list of messages.
    """
    meta = AgentMeta.instance()
    schema = meta.schema_map.get(agent_name)

    if schema is None:
        return f"Error: no output schema configured for agent '{agent_name}'"

    logger.info(f"convert_format: agent={agent_name}, schema={schema}, #messages={len(messages)}")

    converter = StructuredOutputConverter(lm())
    result, error = converter.convert(messages, schema, agent_name)

    if error or result is None:
        return f"Error: conversion failed — {error or 'unknown error'}"

    return json.dumps(result)
