# ABOUTME: Generic FastAPI AG-UI entry point for dynagent use cases (CopilotKit).
# ABOUTME: Drop-in parallel to default_ui.py — wraps create_base_agent() for a React UI.

from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_handler
from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent

logger = get_logger(__name__)


def create_copilotkit_app(agent_name: str = "coordinator", path: str = "/agent") -> FastAPI:
    """Build a FastAPI app that serves a dynagent graph over the AG-UI protocol.

    Mirrors ``default_ui.py``: consuming domains set ``DYNAGENT_CONFIG_ROOT_DIR``
    (per the existing convention) and call this factory. The browser never talks
    to this server directly — a Next.js CopilotRuntime proxy does.

    Args:
        agent_name: AG-UI agent identifier. Must match the Next.js ``agents`` key
            and the React ``agent`` prop. Defaults to ``"coordinator"``.
        path: FastAPI mount path for the AG-UI endpoint. Defaults to ``"/agent"``.

    Returns:
        A configured FastAPI app with the AG-UI route registered.
    """
    from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint

    # Build the graph the same way invoke/stream paths do: shared factory + InMemorySaver.
    graph = create_base_agent(checkpointer=InMemorySaver())  # pyright: ignore[reportCallIssue]

    # Preserve existing Langfuse tracing by injecting the callback into the graph
    # run config — the same handler stream_agent_events / invoke_agent attach.
    langfuse_handler = get_langfuse_handler()
    if langfuse_handler is not None:
        graph = graph.with_config({"callbacks": [langfuse_handler], "recursion_limit": 50})
    else:
        graph = graph.with_config({"recursion_limit": 50})

    agent = LangGraphAgent(
        name=agent_name,
        description="Dynagent multi-agent coordinator served over AG-UI.",
        graph=graph,
    )

    app = FastAPI(title=f"Dynagent AG-UI ({agent_name})")
    add_langgraph_fastapi_endpoint(app, agent, path)

    logger.info(f"Mounted AG-UI agent '{agent_name}' at '{path}'")
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_copilotkit_app(), host="0.0.0.0", port=8000)  # noqa: S104
