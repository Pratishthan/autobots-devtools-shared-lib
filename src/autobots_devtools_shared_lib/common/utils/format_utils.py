import json

from jsonschema import Draft7Validator, ValidationError
from langchain_core.messages import AnyMessage

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


def _validate_output(result: dict, schema: dict) -> list[ValidationError]:
    """Validate the output against the schema.

    Args:
        result: The output to validate.
        schema: The schema to validate against.

    Returns:
        True if the output is valid, False otherwise.
    """
    logger.info(f"validate_output: result={result}, schema={schema}")
    # Call some FOSS Python library to validate the output against the schema.
    validator = Draft7Validator(schema)
    return list(validator.iter_errors(result))


def output_format_converter(
    agent_name: str, messages: list[AnyMessage], validate: bool = False
) -> str:
    """Convert conversation history to structured output.

    Uses the current agent's schema for extraction.

    Args:
        agent_name: Name of the current agent (used to find schema).
        messages: Full conversation history as list of messages.
        validate: Whether to validate the output against the schema.
    """
    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
    from autobots_devtools_shared_lib.dynagent.llm.llm import lm
    from autobots_devtools_shared_lib.dynagent.services.structured_converter import (
        StructuredOutputConverter,
    )

    meta = AgentMeta.instance()
    schema = meta.schema_map.get(agent_name)  # pyright: ignore[reportAttributeAccessIssue]

    if schema is None:
        return f"Error: no output schema configured for agent '{agent_name}'"

    logger.info(f"convert_format: agent={agent_name}, schema={schema}, #messages={len(messages)}")

    converter = StructuredOutputConverter(lm())
    result, error = converter.convert(messages, schema, agent_name)

    if error or result is None:
        return f"Error: conversion failed — {error or 'unknown error'}"

    if validate:
        errors = _validate_output(result, schema)
        if errors:
            return f"Error: validation failed — {', '.join([error.message for error in errors])}"
    return json.dumps(result)
