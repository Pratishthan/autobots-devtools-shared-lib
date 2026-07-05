# ABOUTME: FastAPI AG-UI entry point for the dynagent DEEP engine (CopilotKit).
# ABOUTME: Wraps create_base_deepagent() and serves it over the AG-UI protocol for the React UI.

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_handler
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
from autobots_devtools_shared_lib.dynagent.agents.base_deepagent import create_base_deepagent
from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
    collapse_system_messages,
)
from autobots_devtools_shared_lib.dynagent.ui.rail_stream import RailAGUIAgent

logger = get_logger(__name__)

_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite
    "http://localhost:8080",
]
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ATLAS_UI_ORIGINS", ",".join(_DEFAULT_ORIGINS)).split(",")
    if o.strip()
]


def create_copilotkit_app(agent_name: str | None = None, path: str = "/agent") -> FastAPI:
    """Build a FastAPI app serving a dynagent DEEP-agent graph over the AG-UI protocol."""
    from ag_ui_langgraph import add_langgraph_fastapi_endpoint
    from copilotkit import CopilotKitMiddleware

    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta

    graph_id = agent_name or get_default_agent() or "dynagent"

    graph = create_base_deepagent(
        checkpointer=InMemorySaver(),
        initial_agent_name=agent_name,
        middleware=[CopilotKitMiddleware(), collapse_system_messages],
    )

    langfuse_handler = get_langfuse_handler()
    if langfuse_handler is not None:
        graph = graph.with_config({"callbacks": [langfuse_handler], "recursion_limit": 50})
    else:
        graph = graph.with_config({"recursion_limit": 50})

    mcp_servers = set(AgentMeta.instance().mcp_servers_config.keys())
    agent = RailAGUIAgent(
        name=graph_id,
        description="Dynagent deep-agent coordinator served over AG-UI.",
        graph=graph,
        mcp_servers=mcp_servers,
        main_agent_name=agent_name or get_default_agent(),
    )

    app = FastAPI(title=f"Dynagent AG-UI ({graph_id})")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    add_langgraph_fastapi_endpoint(app, agent, path)

    logger.info(
        f"Mounted CopilotKit AG-UI deep agent graphId='{graph_id}' at '{path}' "
        f"· set the frontend graphId to '{graph_id}' · CORS origins={ALLOWED_ORIGINS}"
    )
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_copilotkit_app(), host="0.0.0.0", port=8000)  # noqa: S104
