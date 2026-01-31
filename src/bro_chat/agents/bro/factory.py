# ABOUTME: Factory function for creating bro agent instances.
# ABOUTME: Assembles agent with middleware stack and step configuration.

import logging
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

from bro_chat.agents.bro.config import get_step_config
from bro_chat.agents.bro.middleware import create_apply_bro_step_config
from bro_chat.agents.bro.state import BroAgentState
from bro_chat.services.document_store import DocumentStore

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)


def create_bro_agent(
    store: DocumentStore | None = None,
    checkpointer: Any = None,
    base_path: Path | str = "vision-docs",
):
    """Create the bro agent with step-based middleware.

    Args:
        store: Document store instance. Created if not provided.
        checkpointer: LangGraph checkpointer for persistence.
        base_path: Base path for document storage.

    Returns:
        Configured bro agent.
    """
    if store is None:
        store = DocumentStore(base_path=base_path)

    if checkpointer is None:
        checkpointer = InMemorySaver()

    step_config = get_step_config(store)
    all_tools = []
    for config in step_config.values():
        all_tools.extend(config["tools"])

    agent = create_agent(
        model,
        name="bro-agent",
        tools=all_tools,
        state_schema=BroAgentState,
        middleware=cast(
            list[AgentMiddleware[Any, Any]],
            [
                create_apply_bro_step_config(store),
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
