# ABOUTME: /mcp-servers router — lists configured servers with a display-only connected pref.
# ABOUTME: Real OAuth connect is deferred; PATCH flips only the display flag (no handshake).

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from autobots_devtools_shared_lib.dynagent.api.resources.tools import group_mcp_tools

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore

_NAMESPACE = "mcp"


def server_abbr(name: str) -> str:
    """Uppercase 2-char abbreviation: first letters of the first two word-parts, else first two chars."""
    parts = [p for p in re.split(r"[-_ ]+", name) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


class _ConnectedBody(BaseModel):
    connected: bool


def build_mcp_servers_router(
    meta: Any,
    prefs_store: PrefsStore,
    user_id_dependency: Any,
) -> APIRouter:
    """Build the /mcp-servers router (list + display-only connected pref)."""
    router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])

    @router.get("")
    async def list_servers(user_id: str = Depends(user_id_dependency)) -> dict[str, Any]:
        grouped, _warnings = group_mcp_tools(meta)
        counts = {g["server"]: len(g["tools"]) for g in grouped}
        prefs = await prefs_store.get(user_id, _NAMESPACE)
        servers = [
            {
                "name": name,
                "abbr": server_abbr(name),
                "connected": prefs.get(name, False),
                "tool_count": counts.get(name, 0),
            }
            for name in meta.mcp_servers_config
        ]
        return {"servers": servers}

    @router.patch("/{name}")
    async def set_connected(
        name: str, body: _ConnectedBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await prefs_store.set(user_id, _NAMESPACE, name, body.connected)
        return {"ok": True}

    return router
