# ABOUTME: Composes the resource-plane routers and registers domain->HTTP error mapping.
# ABOUTME: build_resource_router() mounts threads/skills/tools/mcp-servers under one router.

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from autobots_devtools_shared_lib.dynagent.api.thread_store import (
    ThreadAccessError,
    ThreadNotFoundError,
)

if TYPE_CHECKING:
    from fastapi import FastAPI, Request


def register_exception_handlers(app: FastAPI) -> None:
    """Map store-layer domain errors to typed JSON HTTP responses."""

    @app.exception_handler(ThreadNotFoundError)
    async def _not_found(_request: Request, exc: ThreadNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"thread not found: {exc}"})

    @app.exception_handler(ThreadAccessError)
    async def _forbidden(_request: Request, exc: ThreadAccessError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": f"forbidden: {exc}"})
