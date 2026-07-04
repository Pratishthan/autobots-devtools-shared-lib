# ABOUTME: Loads MCP server tools declared in deep-agents.yaml via langchain-mcp-adapters.
# ABOUTME: Bridges the async client into the sync factory (event-loop-aware asyncio.run).

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any

from autobots_devtools_shared_lib.common.observability import get_logger

logger = get_logger(__name__)


def _run_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    """asyncio.run, falling back to a fresh thread when a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def load_mcp_tools(
    server_names: list[str],
    servers_config: dict[str, dict[str, Any]],
) -> list[Any]:
    """Fetch tools for the referenced MCP servers, prefixed '<server>__<tool>'.

    The prefix avoids collisions with registered dynagent tools. Import is lazy
    so domains without mcp_servers: never need langchain-mcp-adapters installed.
    """
    if not server_names:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient

    connections = {name: servers_config[name] for name in server_names}
    client = MultiServerMCPClient(connections)  # type: ignore[arg-type]

    async def _fetch() -> list[tuple[str, Any]]:
        pairs: list[tuple[str, Any]] = []
        for server_name in server_names:
            pairs.extend(
                (server_name, tool) for tool in await client.get_tools(server_name=server_name)
            )
        return pairs

    tools: list[Any] = []
    for server_name, tool in _run_coro(_fetch()):
        tool.name = f"{server_name}__{tool.name}"
        tools.append(tool)
    logger.info(f"Loaded {len(tools)} MCP tools from servers {server_names}")
    return tools
