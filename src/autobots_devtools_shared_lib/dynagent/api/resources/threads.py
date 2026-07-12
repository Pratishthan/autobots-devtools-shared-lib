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
    ThreadRecord,
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
    create_body_model: type[BaseModel] | None = None,
    on_thread_created: Callable[[ThreadRecord, Any], Awaitable[None]] | None = None,
) -> APIRouter:
    """Build the /threads CRUD router bound to a store + identity dependency.

    A domain may narrow thread creation without owning the router: `create_body_model`
    replaces the default title-only body, so FastAPI rejects an incomplete request before
    any row is written, and `on_thread_created` runs after the row exists (e.g. to seed a
    per-thread workspace context from the fields the domain added).
    """
    router = APIRouter(prefix="/threads", tags=["threads"])
    create_model = create_body_model or _CreateBody

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

    async def create_thread(
        body: _CreateBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, str]:
        record = await thread_store.create(user_id, body.title)
        if on_thread_created is not None:
            await on_thread_created(record, body)
        return {"id": record["id"]}

    # The module runs under `from __future__ import annotations`, so the signature above is
    # stored as the string "_CreateBody". Rebinding to the live class before registration
    # lets FastAPI validate (and document) the domain's body model instead.
    create_thread.__annotations__["body"] = create_model
    router.post("")(create_thread)

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
