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
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from bro_chat.utils.files import list_files, load_prompt, read_file, write_file

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)


# 1. Define the possible workflow steps
DesignerStep = Literal[
    "coordinator",
    "background",
    "service_design",
    "schema_design",
    "behaviour_design",
    "validation_design",
    "lld_consolidator",
]


# 2. Define custom state
class DesignerState(AgentState):
    """State for the designer workflow."""

    current_step: NotRequired[DesignerStep]
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
    message: str, tool_call_id: str, new_step: DesignerStep, **updates
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
    runtime: ToolRuntime[None, DesignerState], next_agent: DesignerStep
) -> Command:
    """Transition to Background step to capture business requirements."""
    logger.info("Tool called: transition_to_background")
    return create_transition_command(
        "Transitioning to Background step for capturing business requirements",
        runtime.tool_call_id or "unknown_tool_call_id",
        new_step=next_agent,
    )


STD_TOOLS = [handoff, read_file, write_file, list_files]

# 5. Step configuration: maps step name to (prompt, tools, required_state)
STEP_CONFIG = {
    "coordinator": {
        "prompt": load_prompt("designer/coordinator"),
        "tools": STD_TOOLS + [],
        "requires": [],
    },
    "background": {
        "prompt": load_prompt("designer/background"),
        "tools": STD_TOOLS + [],
        "requires": [],
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
    current_step = request.state.get("current_step", "coordinator")
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

    # Inject system prompt and step-specific tools
    request = request.override(
        system_message=SystemMessage(content=system_prompt),
        tools=stage_config["tools"],
    )

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
        state_schema=DesignerState,
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
def run_designer_agent(
    user_message: str,
    thread_id: str = "default",
    sdlc_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run the designer agent system.

    Args:
        user_message: The user's input message
        thread_id: Thread ID for conversation persistence
        sdlc_context: Optional SDLC context dictionary

    Returns:
        Dictionary containing the final state and messages
    """
    logger.info(f"Running designer agent for thread_id: {thread_id}")
    agent = create_dynamic_agent()

    initial_state: DesignerState = cast(
        DesignerState, {"messages": [HumanMessage(content=user_message)]}
    )

    if sdlc_context:
        initial_state["sdlc_context"] = sdlc_context

    run_config = {"configurable": {"thread_id": thread_id}}

    result = agent.invoke(initial_state, config=run_config)  # type: ignore[arg-type]

    return result


if __name__ == "__main__":
    # Example usage
    import uuid

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    agent = create_dynamic_agent()
    initial_state: DesignerState = cast(
        DesignerState,
        {
            "messages": [
                HumanMessage(content="Start the design process for a new microservice.")
            ]
        },
    )
    result = agent.invoke(initial_state, config=config)  # type: ignore[arg-type]
    for msg in result["messages"]:
        print(f"{msg.role}: {msg.content}")
