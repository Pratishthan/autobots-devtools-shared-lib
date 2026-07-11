# ABOUTME: TestClient coverage for the threads CRUD router against a dict-backed fake.
# ABOUTME: Covers list/grouping, create, rename, delete+checkpoint clear, 404/403.

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autobots_devtools_shared_lib.dynagent.api.resources.threads import (
    build_threads_router,
    thread_group,
)
from autobots_devtools_shared_lib.dynagent.api.router import register_exception_handlers

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.dynagent.api.thread_store import ThreadRecord


class FakeThreadStore:
    def __init__(self) -> None:
        self.rows: dict[str, ThreadRecord] = {}

    async def list(self, user_id, q=None):
        rows = [r for r in self.rows.values() if r["user_id"] == user_id]
        if q:
            rows = [r for r in rows if q.lower() in r["title"].lower()]
        return sorted(rows, key=lambda r: r["updated_at"], reverse=True)

    async def create(self, user_id, title="New chat"):
        now = datetime.now(UTC)
        rec: ThreadRecord = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        self.rows[rec["id"]] = rec
        return rec

    async def get(self, thread_id):
        return self.rows.get(thread_id)

    async def rename(self, thread_id, title):
        self.rows[thread_id]["title"] = title

    async def delete(self, thread_id):
        self.rows.pop(thread_id, None)

    async def touch(self, thread_id):
        self.rows[thread_id]["updated_at"] = datetime.now(UTC)


@pytest.fixture
def deleted_checkpoints():
    return []


@pytest.fixture
def client(deleted_checkpoints):
    store = FakeThreadStore()

    async def checkpoint_deleter(thread_id: str) -> None:
        deleted_checkpoints.append(thread_id)

    app = FastAPI()
    register_exception_handlers(app)
    app.state.store = store
    app.include_router(
        build_threads_router(
            store, user_id_dependency=lambda: "u1", checkpoint_deleter=checkpoint_deleter
        )
    )
    return TestClient(app)


def test_thread_group_today_vs_earlier():
    now = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)
    assert thread_group(now, now=now) == "Today"
    assert thread_group(now - timedelta(days=2), now=now) == "Earlier"


def test_create_then_list_groups_today(client):
    created = client.post("/threads", json={}).json()
    assert "id" in created
    listed = client.get("/threads").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["title"] == "New chat"
    assert listed[0]["group"] == "Today"


def test_rename_updates_title(client):
    tid = client.post("/threads", json={}).json()["id"]
    resp = client.patch(f"/threads/{tid}", json={"title": "Renamed"})
    assert resp.status_code == 200
    assert client.get("/threads").json()[0]["title"] == "Renamed"


def test_delete_clears_metadata_and_checkpoint(client, deleted_checkpoints):
    tid = client.post("/threads", json={}).json()["id"]
    resp = client.delete(f"/threads/{tid}")
    assert resp.status_code == 200
    assert client.get("/threads").json() == []
    assert deleted_checkpoints == [tid]


def test_rename_unknown_thread_404(client):
    assert client.patch("/threads/does-not-exist", json={"title": "x"}).status_code == 404


def test_rename_empty_title_422(client):
    tid = client.post("/threads", json={}).json()["id"]
    assert client.patch(f"/threads/{tid}", json={"title": ""}).status_code == 422


def test_cross_user_delete_403():
    store = FakeThreadStore()

    owner_app = FastAPI()
    register_exception_handlers(owner_app)
    owner_app.include_router(build_threads_router(store, user_id_dependency=lambda: "owner"))
    rec = TestClient(owner_app).post("/threads", json={}).json()  # thread owned by "owner"

    intruder_app = FastAPI()
    register_exception_handlers(intruder_app)
    intruder_app.include_router(build_threads_router(store, user_id_dependency=lambda: "intruder"))
    assert TestClient(intruder_app).delete(f"/threads/{rec['id']}").status_code == 403
