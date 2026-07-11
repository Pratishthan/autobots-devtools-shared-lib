# ABOUTME: /tools router — enumerates MCP tools grouped by server, degrading gracefully.
# ABOUTME: access READ/WRITE is a write-verb name heuristic (annotations are a later drop-in).

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.agents.deep_mcp import load_mcp_tools

logger = get_logger(__name__)

_WRITE_VERBS = frozenset(
    {
        "create",
        "update",
        "delete",
        "write",
        "set",
        "put",
        "post",
        "patch",
        "remove",
        "insert",
        "add",
        "send",
        "modify",
        "edit",
    }
)


def _short(name: str) -> str:
    """Strip the '<server>__' MCP prefix for display."""
    return name.split("__", 1)[1] if "__" in name else name


def tool_access(name: str) -> str:
    """Classify a tool as WRITE when any '_'-delimited token is a write verb, else READ."""
    tokens = _short(name).lower().replace("-", "_").split("_")
    return "WRITE" if any(token in _WRITE_VERBS for token in tokens) else "READ"


def _describe_tool(tool: Any) -> dict[str, Any]:
    name = getattr(tool, "name", "")
    args = getattr(tool, "args", None) or {}
    return {
        "name": _short(name),
        "description": getattr(tool, "description", "") or "",
        "params": list(args.keys()),
        "access": tool_access(name),
    }


def group_mcp_tools(meta: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """List MCP tools per server. One bad server yields an empty list + a warning."""
    servers: list[dict[str, Any]] = []
    warnings: list[str] = []
    for server in meta.mcp_servers_config:
        try:
            tools = load_mcp_tools([server], meta.mcp_servers_config)
            servers.append({"server": server, "tools": [_describe_tool(t) for t in tools]})
        except Exception as exc:  # degrade, never 500
            logger.warning("tools introspection failed for %s: %s", server, exc)
            servers.append({"server": server, "tools": []})
            warnings.append(f"Cannot load tools from '{server}': {exc}")
    return servers, warnings


def build_tools_router(meta: Any) -> APIRouter:
    """Build the /tools router (introspection-only)."""
    router = APIRouter(prefix="/tools", tags=["tools"])

    @router.get("")
    async def list_tools() -> dict[str, Any]:
        servers, warnings = group_mcp_tools(meta)
        return {"servers": servers, "warnings": warnings}

    return router
