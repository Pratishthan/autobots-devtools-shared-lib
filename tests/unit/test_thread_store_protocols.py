# ABOUTME: Unit tests for the ThreadStore/PrefsStore Protocols and domain errors.
# ABOUTME: A dict-backed fake must structurally satisfy the Protocols.

from datetime import UTC, datetime


def test_fake_satisfies_thread_store_protocol():
    from autobots_devtools_shared_lib.dynagent.api.thread_store import (
        ThreadRecord,
        ThreadStore,
    )

    class FakeThreadStore:
        def __init__(self) -> None:
            self._rows: dict[str, ThreadRecord] = {}

        async def list(self, user_id: str, q: str | None = None) -> list[ThreadRecord]:
            return [r for r in self._rows.values() if r["user_id"] == user_id]

        async def create(self, user_id: str, title: str = "New chat") -> ThreadRecord:
            now = datetime.now(UTC)
            rec: ThreadRecord = {
                "id": "t1",
                "user_id": user_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }
            self._rows[rec["id"]] = rec
            return rec

        async def get(self, thread_id: str) -> ThreadRecord | None:
            return self._rows.get(thread_id)

        async def rename(self, thread_id: str, title: str) -> None:
            self._rows[thread_id]["title"] = title

        async def delete(self, thread_id: str) -> None:
            self._rows.pop(thread_id, None)

        async def touch(self, thread_id: str) -> None:
            self._rows[thread_id]["updated_at"] = datetime.now(UTC)

    store: ThreadStore = FakeThreadStore()
    assert isinstance(store, ThreadStore)


def test_fake_satisfies_prefs_store_protocol():
    from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore

    class FakePrefsStore:
        def __init__(self) -> None:
            self._kv: dict[tuple[str, str, str], bool] = {}

        async def get(self, user_id: str, namespace: str) -> dict[str, bool]:
            return {k[2]: v for k, v in self._kv.items() if k[0] == user_id and k[1] == namespace}

        async def set(self, user_id: str, namespace: str, key: str, value: bool) -> None:
            self._kv[(user_id, namespace, key)] = value

    store: PrefsStore = FakePrefsStore()
    assert isinstance(store, PrefsStore)


def test_domain_errors_are_exceptions():
    from autobots_devtools_shared_lib.dynagent.api.thread_store import (
        ThreadAccessError,
        ThreadNotFoundError,
    )

    assert issubclass(ThreadNotFoundError, Exception)
    assert issubclass(ThreadAccessError, Exception)
