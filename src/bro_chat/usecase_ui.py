# ABOUTME: BRO-specific Chainlit entry point for the bro-chat use case.
# ABOUTME: Wires tracing, OAuth, commands, and the shared streaming helper.

import logging
from typing import Any

import chainlit as cl
from chainlit.types import CommandDict
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langfuse import propagate_attributes

from bro_chat.agents.bro_tools import register_bro_tools
from bro_chat.config.settings import get_settings
from bro_chat.observability.tracing import (
    flush_tracing,
    get_langfuse_handler,
    init_tracing,
)
from bro_chat.utils.formatting import format_structured_output
from dynagent.agents.base_agent import create_base_agent
from dynagent.ui.ui_utils import stream_agent_events

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
settings = get_settings()

# Registration must precede AgentMeta.instance() (called inside create_base_agent).
register_bro_tools()

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
    """Handle OAuth callback from GitHub.

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


def get_preloaded_prompts(msg: Any) -> str:
    """Return the effective prompt string for a message, honouring slash commands."""
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
    agent = create_base_agent()
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
    }

    # Add Langfuse handler if available
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

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
    app_name = "coordinator"

    input_state: dict[str, Any] = {
        "messages": [{"role": "user", "content": prompt}],
        "user_name": user_name,
        "app_name": app_name,
        "session_id": cl.context.session.thread_id,
    }

    try:
        # Use propagate_attributes to tag user and session for Langfuse tracking
        with propagate_attributes(
            user_id=user_name[:200],  # Ensure ≤200 chars as per Langfuse requirements
            session_id=cl.context.session.thread_id[:200],  # Use thread_id as session
        ):
            await stream_agent_events(
                agent,
                input_state,
                config,
                on_structured_output=format_structured_output,
            )
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
