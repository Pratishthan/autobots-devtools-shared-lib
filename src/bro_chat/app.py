# ABOUTME: Chainlit application entry point for bro-chat.
# ABOUTME: Handles chat messages, OAuth authentication, and agent orchestration.

import logging

import chainlit as cl
from chainlit.types import ThreadDict

from bro_chat.agents.crew import create_crew, run_chat
from bro_chat.config.settings import get_settings
from bro_chat.observability.tracing import flush_tracing, init_tracing

logger = logging.getLogger(__name__)
settings = get_settings()


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


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize chat session."""
    init_tracing(settings)

    crew = create_crew(settings)
    cl.user_session.set("crew", crew)

    await cl.Message(
        content="Hello! I'm your AI assistant. How can I help you today?"
    ).send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Resume a previous chat session."""
    crew = create_crew(settings)
    cl.user_session.set("crew", crew)

    logger.info(f"Resumed chat thread: {thread.get('id', 'unknown')}")


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """
    Handle incoming chat messages.

    Args:
        message: The incoming message from the user.
    """
    crew = cl.user_session.get("crew")

    if crew is None:
        crew = create_crew(settings)
        cl.user_session.set("crew", crew)

    try:
        response = await run_chat(crew, message.content)
        await cl.Message(content=response).send()

    except Exception as e:
        logger.exception("Error processing message")
        await cl.Message(content=f"Sorry, I encountered an error: {e}").send()

    finally:
        flush_tracing()


@cl.on_stop
def on_stop() -> None:
    """Handle chat stop."""
    flush_tracing()
    logger.info("Chat session stopped")


if __name__ == "__main__":
    import chainlit.cli

    chainlit.cli.run_chainlit(target=__file__)
