# ABOUTME: DB-agnostic Protocols for the AMA thread index and per-user UI prefs.
# ABOUTME: mer implements these over Postgres; shared-lib tests use dict-backed fakes.

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Protocol, TypedDict, runtime_checkable


class ThreadRecord(TypedDict):
    """Left-rail metadata for one conversation. Never holds message content."""

    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@runtime_checkable
class ThreadStore(Protocol):
    """Index of conversations (left rail). Content lives in the checkpointer."""

    async def list(self, user_id: str, q: str | None = None) -> list[ThreadRecord]: ...

    async def create(self, user_id: str, title: str = "New chat") -> ThreadRecord: ...

    async def get(self, thread_id: str) -> ThreadRecord | None: ...

    async def rename(self, thread_id: str, title: str) -> None: ...

    async def delete(self, thread_id: str) -> None: ...

    async def touch(self, thread_id: str) -> None: ...


@runtime_checkable
class PrefsStore(Protocol):
    """Narrow per-user KV for display-only UI prefs (namespace = 'skills' | 'mcp')."""

    async def get(self, user_id: str, namespace: str) -> dict[str, bool]: ...

    async def set(self, user_id: str, namespace: str, key: str, value: bool) -> None: ...


class ThreadNotFoundError(Exception):
    """Raised when a thread_id has no metadata row."""


class ThreadAccessError(Exception):
    """Raised when a user_id does not own the requested thread."""
