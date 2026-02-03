import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal, NotRequired, cast

from dotenv import load_dotenv
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    SummarizationMiddleware,
    wrap_model_call,
)
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from bro_chat.models.outputs import JokeOutput, MathOutput
from bro_chat.utils.files import list_files, load_prompt, read_file, write_file

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)


# 1. Define the possible workflow steps
AgentList = Literal[
    "joke_agent",
    "math_agent",
]


# 2. Define custom state
class DynamicAgentState(AgentState):
    """State for the dynamic agent workflow."""

    current_step: NotRequired[AgentList]
    sdlc_context: NotRequired[dict[str, Any]]
    app_type: NotRequired[str]
    app_name: NotRequired[str]
    jira_number: NotRequired[str]


# 3. Helper functions for creating Command objects
def create_error_command(message: str, tool_call_id: str) -> Command:
    """Create a Command for error/validation failure responses."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


def create_transition_command(
    message: str, tool_call_id: str, new_step: AgentList, **updates
) -> Command:
    """Create a Command for successful state transitions."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ],
            "current_step": new_step,
            **updates,
        }
    )


# 4. Create tools that manage workflow state transitions
@tool
def handoff(
    runtime: ToolRuntime[None, DynamicAgentState], next_agent: AgentList
) -> Command:
    """Transition to Background step to capture business requirements."""
    logger.info(f"Handoff Tool called: {next_agent}")
    return create_transition_command(
        f"Handoff to {next_agent}",
        runtime.tool_call_id or "unknown_tool_call_id",
        new_step=next_agent,
    )


STD_TOOLS = [handoff, read_file, write_file, list_files]

# 5. Step configuration: maps step name to config dict
# Config includes: prompt, tools, required_state, response_format
STEP_CONFIG = {
    "joke_agent": {
        "prompt": load_prompt("designer/joke_agent"),
        "tools": STD_TOOLS + [],
        "requires": [],
        "response_format": JokeOutput,
    },
    "math_agent": {
        "prompt": load_prompt("designer/math_agent"),
        "tools": STD_TOOLS + [],
        "requires": [],
        "response_format": MathOutput,
    },
}


# 6. Create step-based middleware (async version for streaming support)
@wrap_model_call  # type: ignore[arg-type]
async def apply_step_config(
    request: ModelRequest,
    handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
) -> ModelResponse:
    """Configure agent behavior based on the current step."""
    # Get current step (defaults to coordinator for first interaction)
    current_step = request.state.get("current_step", "math_agent")
    message_count = len(request.messages)
    logger.info(
        f"Applying step config for: {current_step}. Message count: {message_count}"
    )

    # Look up step configuration
    stage_config = STEP_CONFIG[current_step]

    # Validate required state exists
    for key in stage_config["requires"]:
        if request.state.get(key) is None:
            raise ValueError(f"{key} must be set before reaching {current_step}")

    # Format prompt with state values (supports {background_completed}, etc.)
    # Provide defaults for optional fields
    format_values = {
        # "background_completed": False,
        **request.state,  # Override with actual state values
    }
    system_prompt = stage_config["prompt"].format(**format_values)

    # Build request overrides
    overrides: dict[str, Any] = {
        "system_message": SystemMessage(content=system_prompt),
        "tools": stage_config["tools"],
    }

    # Add response_format if specified
    if response_format := stage_config.get("response_format"):
        overrides["response_format"] = response_format

    # Inject system prompt, tools, and response format
    request = request.override(**overrides)

    return await handler(request)


# 7. Collect all tools from all step configurations
all_tools = []
for config in STEP_CONFIG.values():
    all_tools.extend(config["tools"])


# 8. Create the agent with step-based configuration
def create_dynamic_agent(checkpointer=None):
    """Create the designer agent with step-based middleware."""
    if checkpointer is None:
        checkpointer = InMemorySaver()

    agent = create_agent(
        model,
        name="designer-agent",
        tools=all_tools,
        state_schema=DynamicAgentState,
        middleware=cast(
            list[AgentMiddleware[Any, Any]],
            [
                apply_step_config,
                SummarizationMiddleware(
                    model=model,
                    trigger=("fraction", 0.6),
                    keep=("messages", 20),
                ),
            ],
        ),
        checkpointer=checkpointer,
    )

    return agent


# 9. Main execution function
async def run_dynagent(
    user_message: str,
    config: RunnableConfig,
) -> dict[str, Any] | None:
    """
    Run the dynamic agent system and return structured output.

    Args:
        user_message: The user's input message
        config: Configuration for the runnable agent

    Returns:
        Structured response dict if available, None otherwise
    """
    logger.info(f"Running dynamic agent for config: {config}")
    agent = create_dynamic_agent()
    # Pass dict directly - LangGraph will convert to proper state type
    initial_state = {"messages": [HumanMessage(content=user_message)]}

    result = await agent.ainvoke(initial_state, config=config)  # type: ignore[arg-type]

    # Extract structured response if available
    structured = result.get("structured_response")
    if structured:
        logger.info(f"Structured response: {structured}")
        return structured

    return None


if __name__ == "__main__":
    # Example usage
    import asyncio
    import json
    import uuid

    from bro_chat.utils.formatting import format_structured_output

    thread_id = str(uuid.uuid4())

    run_config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 50,
    }

    result = asyncio.run(
        run_dynagent(
            "What is the square root of 16?",
            config=run_config,
        )
    )

    if result:
        # Log JSON for debugging
        logger.info(f"Structured output (JSON): {json.dumps(result, indent=2)}")

        # Display Markdown for user
        print("\n" + "=" * 50)
        print(format_structured_output(result, "math"))
        print("=" * 50)
