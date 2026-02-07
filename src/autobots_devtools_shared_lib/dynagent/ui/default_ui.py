# ABOUTME: Generic Chainlit entry point for dynagent use cases with zero custom UI.
# ABOUTME: No tracing, no commands, no OAuth — just agent streaming via ui_utils.

import logging
from typing import Any

import chainlit as cl
from langchain_core.runnables import RunnableConfig

from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent
from autobots_devtools_shared_lib.dynagent.ui.ui_utils import stream_agent_events

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@cl.on_chat_start
async def start():
    """Create the base agent once and store it in the Chainlit session."""
    agent = create_base_agent(agent_name="coordinator")
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
        await cl.Message(
            content="Error: Session initialization failed. Please refresh."
        ).send()
        return

    input_state: dict[str, Any] = {
        "messages": [{"role": "user", "content": message.content}],
        "agent_name": "coordinator",
        "session_id": cl.context.session.thread_id,
    }

    await stream_agent_events(agent, input_state, config)


@cl.on_stop
def on_stop() -> None:
    """Handle chat stop."""
    logger.info("Chat session stopped")


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
