# ABOUTME: Per-session MCP client connection manager.
# ABOUTME: Creates, caches, and tears down MCP connections keyed by (server_name, session_id).

from __future__ import annotations

import threading
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.dynagent.mcp.config import McpServerConfig, McpTransport
from autobots_devtools_shared_lib.dynagent.mcp.registry import McpServerRegistry

logger = get_logger(__name__)

_instance: McpSessionManager | None = None
_lock = threading.Lock()


class _McpConnection:
    """Holds a ClientSession and its async exit stack for cleanup."""

    def __init__(self, session: ClientSession, exit_stack: AsyncExitStack) -> None:
        self.session = session
        self.exit_stack = exit_stack

    async def close(self) -> None:
        await self.exit_stack.aclose()


class McpSessionManager:
    """Manages per-session MCP client connections."""

    def __init__(self) -> None:
        self._connections: dict[tuple[str, str], object] = {}

    @classmethod
    def instance(cls) -> McpSessionManager:
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    @classmethod
    def reset(cls) -> None:
        global _instance
        _instance = None

    async def get_or_create(
        self, server_name: str, session_id: str, auth_token: str | None
    ) -> object:
        """Return cached connection or create a new one."""
        key = (server_name, session_id)
        if key in self._connections:
            return self._connections[key].session  # type: ignore[union-attr]

        # Validate server exists in registry (raises KeyError if not found)
        config = McpServerRegistry.instance().get(server_name)
        conn = await self._create_connection(config, auth_token)
        self._connections[key] = conn
        logger.info("Created MCP connection: server=%s session=%s", server_name, session_id)
        return conn.session  # type: ignore[union-attr]

    async def _create_connection(
        self, config: McpServerConfig, auth_token: str | None
    ) -> _McpConnection:
        """Create a new MCP client connection based on transport type."""
        stack = AsyncExitStack()

        if config.transport == McpTransport.STDIO:
            session = await self._connect_stdio(stack, config, auth_token)
        elif config.transport == McpTransport.STREAMABLE_HTTP:
            session = await self._connect_http(stack, config, auth_token)
        else:
            msg = f"Unsupported transport: {config.transport}"
            raise ValueError(msg)

        await session.initialize()
        return _McpConnection(session=session, exit_stack=stack)

    async def _connect_stdio(
        self, stack: AsyncExitStack, config: McpServerConfig, auth_token: str | None
    ) -> ClientSession:
        """Create a stdio MCP connection."""
        env = dict(config.env) if config.env else {}
        if auth_token and config.auth_state_key:
            env_key = f"{config.auth_state_key.upper()}_API_TOKEN"
            env[env_key] = auth_token

        params = StdioServerParameters(
            command=config.command or "",
            args=config.args or [],
            env=env if env else None,
        )
        read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
        return await stack.enter_async_context(ClientSession(read_stream, write_stream))

    async def _connect_http(
        self, stack: AsyncExitStack, config: McpServerConfig, auth_token: str | None
    ) -> ClientSession:
        """Create a streamable HTTP MCP connection."""
        import httpx

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        http_client = (
            await stack.enter_async_context(httpx.AsyncClient(headers=headers)) if headers else None
        )
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client(config.url or "", http_client=http_client)
        )
        return await stack.enter_async_context(ClientSession(read_stream, write_stream))

    async def close_session(self, session_id: str) -> None:
        """Tear down all MCP connections for a session."""
        keys_to_remove = [k for k in self._connections if k[1] == session_id]
        for key in keys_to_remove:
            conn = self._connections.pop(key)
            try:
                await conn.close()  # type: ignore[union-attr]
            except Exception:
                logger.exception("Error closing MCP connection %s", key)
        if keys_to_remove:
            logger.info(
                "Closed %d MCP connection(s) for session %s", len(keys_to_remove), session_id
            )

    async def close_all(self) -> None:
        """Shutdown hook — close all connections."""
        for key, conn in list(self._connections.items()):
            try:
                await conn.close()  # type: ignore[union-attr]
            except Exception:
                logger.exception("Error closing MCP connection %s", key)
        self._connections.clear()
        logger.info("Closed all MCP connections")
