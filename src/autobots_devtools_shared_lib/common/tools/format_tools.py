# ABOUTME: Format conversion tool for structured output extraction.
# ABOUTME: Wraps StructuredOutputConverter; reads schema from AgentMeta.

from langchain.tools import ToolException, ToolRuntime, tool

from autobots_devtools_shared_lib.common.utils.format_utils import output_format_converter
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent


@tool
def output_format_converter_tool(
    runtime: ToolRuntime[None, Dynagent], validate: bool = False
) -> str:
    """
    Tool wrapper for output format conversion.
    Args:
        validate: Whether to validate the output against the schema.
    Returns:
        Structured output as JSON string or error message.
    """
    agent_name = runtime.state.get("agent_name")

    if not agent_name:
        raise ToolException("agent_name not found in runtime state")

    messages = runtime.state.get("messages", [])
    return output_format_converter(agent_name, messages, validate)
