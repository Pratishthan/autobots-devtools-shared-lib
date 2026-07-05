# ABOUTME: Mounts the CopilotKit AG-UI streaming endpoint (RailAGUIAgent) on a FastAPI app.
# ABOUTME: AG-UI-specific; lazily imports ag_ui_langgraph so non-UI paths never need it.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.ui.rail_stream import RailAGUIAgent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI

logger = get_logger(__name__)


def mount_agui_endpoint(
    app: FastAPI,
    graph: Any,
    *,
    graph_id: str,
    mcp_servers: set[str],
    main_agent_name: str | None = None,
    path: str = "/agent",
    on_run_finished: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    """Wrap `graph` in a RailAGUIAgent and mount it over the AG-UI protocol at `path`."""
    from ag_ui_langgraph import add_langgraph_fastapi_endpoint

    agent = RailAGUIAgent(
        name=graph_id,
        description="Dynagent deep-agent coordinator served over AG-UI.",
        graph=graph,
        mcp_servers=mcp_servers,
        main_agent_name=main_agent_name,
        on_run_finished=on_run_finished,
    )
    add_langgraph_fastapi_endpoint(app, agent, path)
    logger.info("Mounted AG-UI deep agent graphId='%s' at '%s'", graph_id, path)
