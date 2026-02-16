# ABOUTME: Generic Chainlit entry point for dynagent use cases with zero custom UI.
# ABOUTME: No tracing, no commands, no OAuth — just agent streaming via ui_utils.

from typing import TYPE_CHECKING, Any

import chainlit as cl

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.trace_metadata import TraceMetadata

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent
from autobots_devtools_shared_lib.dynagent.ui.ui_utils import stream_agent_events

logger = get_logger(__name__)

# Uncomment and customize the following if OAuth is needed
# @cl.oauth_callback  # type: ignore[arg-type]
# def oauth_callback(
#     provider_id: str,
#     token: str,  #  <Add this> noqa: ARG001
#     raw_user_data: dict,
#     default_user: cl.User,
# ) -> cl.User | None:
#     """Handle OAuth callback from GitHub.

#     Args:
#         provider_id: The OAuth provider ID (e.g., "github").
#         token: The OAuth access token.
#         raw_user_data: Raw user data from the provider.
#         default_user: Default user object created by Chainlit.

#     Returns:
#         The authenticated user or None if authentication fails.
#     """
#     if provider_id != "github":
#         logger.warning(f"Unsupported OAuth provider: {provider_id}")
#         return None

#     username = raw_user_data.get("login", "unknown")
#     logger.info(f"User authenticated via GitHub: {username}")
#     return default_user


@cl.on_chat_start
async def start():
    """Create the base agent once and store it in the Chainlit session."""
    agent = create_base_agent(initial_agent_name="coordinator")  # pyright: ignore[reportCallIssue]
    cl.user_session.set("agent", agent)
    await cl.Message(content="Hello, how can I help you today?").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Route an incoming message through the agent via shared streaming."""
    config: RunnableConfig = {
        "configurable": {
            "thread_id": cl.context.session.thread_id,
        },
        "recursion_limit": 50,
    }

    agent = cl.user_session.get("agent")

    if not agent:
        await cl.Message(content="Error: Session initialization failed. Please refresh.").send()
        return

    input_state: dict[str, Any] = {
        "messages": [{"role": "user", "content": message.content}],
        "agent_name": "coordinator",
    }

    # Create trace metadata with session correlation
    trace_metadata = TraceMetadata.create(session_id=cl.context.session.thread_id)

    await stream_agent_events(agent, input_state, config, trace_metadata=trace_metadata)  # pyright: ignore[reportCallIssue]


@cl.on_stop
def on_stop() -> None:
    """Handle chat stop."""
    logger.info("Chat session stopped")


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
