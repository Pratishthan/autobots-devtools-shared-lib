# ABOUTME: Generic FastAPI AG-UI entry point for dynagent use cases (CopilotKit).
# ABOUTME: Drop-in parallel to default_ui.py — wraps create_base_agent() for a React UI.

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.observability.tracing import get_langfuse_handler
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent

logger = get_logger(__name__)

# Origins the browser UI is served from. Override via env in deployment.
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
    """Build a FastAPI app that serves a dynagent graph over the AG-UI protocol."""
    from ag_ui_langgraph import add_langgraph_fastapi_endpoint
    from copilotkit import LangGraphAGUIAgent

    # Derive the graph id from the configured default agent so the v2 frontend
    # route can target it. The operator should set the frontend's graphId to the
    # value logged below.
    graph_id = agent_name or get_default_agent() or "dynagent"

    graph = create_base_agent(  # pyright: ignore[reportCallIssue]
        checkpointer=InMemorySaver(),
        copilotkit=True,
    )

    langfuse_handler = get_langfuse_handler()
    if langfuse_handler is not None:
        graph = graph.with_config({"callbacks": [langfuse_handler], "recursion_limit": 50})
    else:
        graph = graph.with_config({"recursion_limit": 50})

    agent = LangGraphAGUIAgent(
        name=graph_id,
        description="Dynagent multi-agent coordinator served over AG-UI.",
        graph=graph,
    )

    app = FastAPI(title=f"Dynagent AG-UI ({graph_id})")

    # ── CORS: the React UI calls this server directly (no Next.js proxy) ──────
    # allow_credentials=True is required because the UI sends credentials:"include";
    # that forbids a wildcard origin, so list exact origins instead of "*".
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
        f"Mounted CopilotKit AG-UI agent graphId='{graph_id}' at '{path}' "
        f"· set the frontend graphId to '{graph_id}' · CORS origins={ALLOWED_ORIGINS}"
    )
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_copilotkit_app(), host="0.0.0.0", port=8000)  # noqa: S104
