# ABOUTME: Format conversion tool for structured output extraction.
# ABOUTME: Wraps StructuredOutputConverter; reads schema from AgentMeta.

from langchain.tools import ToolRuntime, tool

from autobots_devtools_shared_lib.dynagent.models.state import Dynagent
from autobots_devtools_shared_lib.dynagent.utils.format_utils import output_format_converter


@tool
def output_format_converter_tool(
    runtime: ToolRuntime[None, Dynagent], model_name: str = "gemini-2.0-flash"
) -> str:
    """Convert conversation history to structured output."""
    agent_name = runtime.state.get("agent_name", "coordinator")
    messages = runtime.state.get("messages", [])
    return output_format_converter(agent_name, messages, model_name)
