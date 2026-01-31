import logging
from collections import deque

import chainlit as cl
from chainlit.types import CommandDict
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

from bro_chat.agents.dynagent import create_dynamic_agent
from bro_chat.config.settings import get_settings
from bro_chat.observability.tracing import (
    flush_tracing,
    get_langfuse_handler,
    init_tracing,
)

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
settings = get_settings()


commands: list[CommandDict] = [
    {
        "id": "Joke-Agent",
        "icon": "workflow",
        "description": "Call Joke Agent",
        "button": False,
        "persistent": True,
    },
    {
        "id": "Math-Agent",
        "icon": "briefcase-business",
        "description": "Call Math Agent",
        "button": False,
        "persistent": True,
    },
]


@cl.oauth_callback  # type: ignore[arg-type]
def oauth_callback(
    provider_id: str,
    token: str,  # noqa: ARG001
    raw_user_data: dict,
    default_user: cl.User,
) -> cl.User | None:
    """
    Handle OAuth callback from GitHub.

    Args:
        provider_id: The OAuth provider ID (e.g., "github").
        token: The OAuth access token.
        raw_user_data: Raw user data from the provider.
        default_user: Default user object created by Chainlit.

    Returns:
        The authenticated user or None if authentication fails.
    """
    if provider_id != "github":
        logger.warning(f"Unsupported OAuth provider: {provider_id}")
        return None

    username = raw_user_data.get("login", "unknown")
    logger.info(f"User authenticated via GitHub: {username}")
    return default_user


def get_preloaded_prompts(msg: cl.Message) -> str:
    if msg.command == "View-Context":
        return "Get and display the current SDLC context using get_context tool"
    elif msg.command == "Edit-Context":
        return "Start LLD Consolidator Assistant"
    else:
        return msg.content


@cl.on_chat_start
async def start():
    # Create agent instance once and store it in session
    init_tracing(settings)
    agent = create_dynamic_agent()
    cl.user_session.set("agent", agent)
    await cl.context.emitter.set_commands(commands)
    await cl.Message(content="Hello, how can I help you today?").send()


@cl.on_message
async def on_message(message: cl.Message):
    config: RunnableConfig = {
        "configurable": {
            "thread_id": cl.context.session.thread_id,
        },
        "recursion_limit": 50,
        # This thread_1 will be used for individual testing
        # "configurable": {"thread_id": "thread_1"},
    }

    # Add Langfuse handler if available
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

    msg = cl.Message(content="")
    tool_steps = {}  # Track tool steps by unique run_id
    tool_step_queue = deque(maxlen=3)  # Keep only last 3 tool steps

    await msg.send()  # Send empty message first to start streaming

    prompt = get_preloaded_prompts(message)

    # Reuse the same agent instance from session
    agent = cl.user_session.get("agent")
    user = cl.user_session.get("user")

    if not agent or not user:
        await cl.Message(
            content="Error: Session initialization failed. Please refresh."
        ).send()
        return

    user_name = user.identifier
    agent_name = "designer"

    try:
        # Stream events from the agent for detailed tracking
        async for event in agent.astream_events(
            {
                "messages": [{"role": "user", "content": prompt}],
                "user_name": user_name,
                "agent_name": agent_name,
            },
            config=RunnableConfig(**config),
            version="v2",
        ):
            kind = event["event"]

            # Stream AI response text
            if kind == "on_chat_model_stream":
                content = event.get("data", {}).get("chunk", {}).content
                if content:
                    # Handle content as list or string
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, str):
                                await msg.stream_token(block)
                            elif hasattr(block, "text"):
                                await msg.stream_token(block.text)
                            elif isinstance(block, dict) and "text" in block:
                                await msg.stream_token(block["text"])
                    else:
                        await msg.stream_token(content)

            # Display tool calls using Steps (collapsible)
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event["data"].get("input", {})
                run_id = event.get("run_id")  # Use unique run_id

                # Remove oldest step if we're at max capacity
                if len(tool_step_queue) >= 3:
                    old_run_id = tool_step_queue.popleft()
                    if old_run_id in tool_steps:
                        old_step = tool_steps[old_run_id]
                        await old_step.remove()
                        del tool_steps[old_run_id]

                async with cl.Step(name=f"🛠️ {tool_name}", type="tool") as step:
                    step.input = tool_input
                    tool_steps[run_id] = step
                    tool_step_queue.append(run_id)

            # Display tool results
            elif kind == "on_tool_end":
                run_id = event.get("run_id")
                output = event["data"].get("output", "")

                if run_id in tool_steps:
                    step = tool_steps[run_id]
                    step.output = str(output)[:1000]  # Limit output length
                    await step.update()

        await msg.update()
    finally:
        flush_tracing()


@cl.on_stop
def on_stop() -> None:
    """Handle chat stop."""
    flush_tracing()
    logger.info("Chat session stopped")


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
