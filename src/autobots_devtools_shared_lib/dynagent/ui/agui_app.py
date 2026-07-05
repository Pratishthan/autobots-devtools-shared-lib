# ABOUTME: create_agui_app composes the AG-UI streaming plane with the REST resource plane.
# ABOUTME: One create_base_deepagent graph + one checkpointer serve /agent and /threads,/skills,...

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autobots_devtools_shared_lib.common.observability import get_langfuse_handler, get_logger
from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_default_agent
from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta
from autobots_devtools_shared_lib.dynagent.agents.base_deepagent import create_base_deepagent
from autobots_devtools_shared_lib.dynagent.api.router import (
    build_resource_router,
    register_exception_handlers,
)
from autobots_devtools_shared_lib.dynagent.ui.agui_endpoint import mount_agui_endpoint
from autobots_devtools_shared_lib.dynagent.ui.collapse_system_messages import (
    collapse_system_messages,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore, ThreadStore

logger = get_logger(__name__)

_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]


def _resolve_origins(cors_origins: list[str] | None) -> list[str]:
    if cors_origins is not None:
        return cors_origins
    raw = os.getenv("ATLAS_UI_ORIGINS", ",".join(_DEFAULT_ORIGINS))
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_agui_app(
    *,
    checkpointer: Any,
    thread_store: ThreadStore,
    prefs_store: PrefsStore,
    backend: Any,
    user_id_dependency: Callable[..., Any],
    agent_name: str | None = None,
    checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None,
    agent_factory: Callable[..., Any] = create_base_deepagent,
    cors_origins: list[str] | None = None,
    path: str = "/agent",
) -> FastAPI:
    """Build the FastAPI app serving the AG-UI stream + client-agnostic resource routers.

    Both planes share one deep-agent graph and one checkpointer. Injected stores replace
    the spike's module-level InMemorySaver; CORS origins and identity are configuration.
    """
    from copilotkit import CopilotKitMiddleware

    meta = AgentMeta.instance()
    graph_id = agent_name or get_default_agent() or "dynagent"

    graph = agent_factory(
        checkpointer=checkpointer,
        initial_agent_name=agent_name,
        middleware=[CopilotKitMiddleware(), collapse_system_messages],
    )
    langfuse_handler = get_langfuse_handler()
    config: dict[str, Any] = {"recursion_limit": 50}
    if langfuse_handler is not None:
        config["callbacks"] = [langfuse_handler]
    graph = graph.with_config(config)

    origins = _resolve_origins(cors_origins)
    app = FastAPI(title=f"Dynagent AG-UI ({graph_id})")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(
        build_resource_router(
            meta=meta,
            thread_store=thread_store,
            prefs_store=prefs_store,
            backend=backend,
            user_id_dependency=user_id_dependency,
            checkpoint_deleter=checkpoint_deleter,
        )
    )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "graph": graph_id}

    mount_agui_endpoint(
        app,
        graph,
        graph_id=graph_id,
        mcp_servers=set(meta.mcp_servers_config.keys()),
        main_agent_name=agent_name or get_default_agent(),
        path=path,
        on_run_finished=thread_store.touch,
    )
    logger.info("create_agui_app ready · graphId='%s' · CORS origins=%s", graph_id, origins)
    return app
