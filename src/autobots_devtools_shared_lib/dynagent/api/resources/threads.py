# ABOUTME: /threads router — the only stateful, per-user resource surface.
# ABOUTME: Metadata-only CRUD over ThreadStore; DELETE also clears checkpoint state.

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from autobots_devtools_shared_lib.dynagent.api.thread_store import (
    ThreadAccessError,
    ThreadNotFoundError,
    ThreadStore,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def thread_group(updated_at: datetime, *, now: datetime | None = None) -> str:
    """Bucket a thread into 'Today' or 'Earlier' by UTC calendar date."""
    ref = now or datetime.now(UTC)
    return "Today" if updated_at.date() == ref.date() else "Earlier"


class _CreateBody(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=200)


class _RenameBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)


async def _require_owned(store: ThreadStore, thread_id: str, user_id: str) -> None:
    record = await store.get(thread_id)
    if record is None:
        raise ThreadNotFoundError(thread_id)
    if record["user_id"] != user_id:
        raise ThreadAccessError(thread_id)


def build_threads_router(
    thread_store: ThreadStore,
    user_id_dependency: Callable[..., Any],
    checkpoint_deleter: Callable[[str], Awaitable[None]] | None = None,
) -> APIRouter:
    """Build the /threads CRUD router bound to a store + identity dependency."""
    router = APIRouter(prefix="/threads", tags=["threads"])

    @router.get("")
    async def list_threads(
        q: str | None = None, user_id: str = Depends(user_id_dependency)
    ) -> list[dict[str, Any]]:
        records = await thread_store.list(user_id, q)
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "group": thread_group(r["updated_at"]),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in records
        ]

    @router.post("")
    async def create_thread(
        body: _CreateBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, str]:
        record = await thread_store.create(user_id, body.title)
        return {"id": record["id"]}

    @router.patch("/{thread_id}")
    async def rename_thread(
        thread_id: str, body: _RenameBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await _require_owned(thread_store, thread_id, user_id)
        await thread_store.rename(thread_id, body.title)
        return {"ok": True}

    @router.delete("/{thread_id}")
    async def delete_thread(
        thread_id: str, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await _require_owned(thread_store, thread_id, user_id)
        await thread_store.delete(thread_id)
        if checkpoint_deleter is not None:
            await checkpoint_deleter(thread_id)
        return {"ok": True}

    return router
