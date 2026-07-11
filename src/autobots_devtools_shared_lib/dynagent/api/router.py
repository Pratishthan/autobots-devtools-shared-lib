# ABOUTME: Composes the resource-plane routers and registers domain->HTTP error mapping.
# ABOUTME: build_resource_router() mounts threads/skills/tools/mcp-servers under one router.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from autobots_devtools_shared_lib.dynagent.api.resources.mcp_servers import (
    build_mcp_servers_router,
)
from autobots_devtools_shared_lib.dynagent.api.resources.skills import build_skills_router
from autobots_devtools_shared_lib.dynagent.api.resources.threads import build_threads_router
from autobots_devtools_shared_lib.dynagent.api.resources.tools import build_tools_router
from autobots_devtools_shared_lib.dynagent.api.thread_store import (
    ThreadAccessError,
    ThreadNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI, Request

    from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore, ThreadStore


def register_exception_handlers(app: FastAPI) -> None:
    """Map store-layer domain errors to typed JSON HTTP responses."""

    @app.exception_handler(ThreadNotFoundError)
    async def _not_found(_request: Request, exc: ThreadNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"thread not found: {exc}"})

    @app.exception_handler(ThreadAccessError)
    async def _forbidden(_request: Request, exc: ThreadAccessError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": f"forbidden: {exc}"})


def build_resource_router(
    *,
    meta: Any,
    thread_store: ThreadStore,
    prefs_store: PrefsStore,
    backend: Any,
    user_id_dependency: Callable[..., Any],
    checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None,
) -> APIRouter:
    """Compose the four resource routers into one client-agnostic APIRouter."""
    router = APIRouter()
    router.include_router(
        build_threads_router(thread_store, user_id_dependency, checkpoint_deleter)
    )
    router.include_router(build_skills_router(meta, backend, prefs_store, user_id_dependency))
    router.include_router(build_tools_router(meta))
    router.include_router(build_mcp_servers_router(meta, prefs_store, user_id_dependency))
    return router
