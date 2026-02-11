import json

from langchain_core.messages import AnyMessage

from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.llm.llm import lm
from autobots_devtools_shared_lib.dynagent.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.services.structured_converter import (
    StructuredOutputConverter,
)

logger = get_logger(__name__)


def output_format_converter(
    agent_name: str, messages: list[AnyMessage], model_name: str = "gemini-2.0-flash"
) -> str:
    """Convert conversation history to structured output.

    Uses the current agent's schema for extraction.

    Args:
        model_name: Reserved for future model selection. Currently uses the default LM.
    """
    meta = AgentMeta.instance()
    schema_path = meta.schema_path_map.get(agent_name)

    if not schema_path:
        return f"Error: no output schema configured for agent '{agent_name}'"

    logger.info(f"convert_format: agent={agent_name}, schema={schema_path}, model={model_name}")

    converter = StructuredOutputConverter(lm())
    result, error = converter.convert(messages, schema_path, agent_name)

    if error or result is None:
        return f"Error: conversion failed — {error or 'unknown error'}"

    return json.dumps(result)
