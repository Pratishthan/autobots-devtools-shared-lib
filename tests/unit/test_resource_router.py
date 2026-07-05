# ABOUTME: Composition test: build_resource_router mounts all four resource routes.
# ABOUTME: Uses dict-backed fakes + monkeypatched discovery; asserts routes + error mapping.

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.skills as skills_mod
import autobots_devtools_shared_lib.dynagent.api.resources.tools as tools_mod
from autobots_devtools_shared_lib.dynagent.api.router import (
    build_resource_router,
    register_exception_handlers,
)


class FakeThreadStore:
    def __init__(self):
        self.rows = {}

    async def list(self, user_id, q=None):
        return []

    async def create(self, user_id, title="New chat"):
        rec = {
            "id": "t1",
            "user_id": user_id,
            "title": title,
            "created_at": None,
            "updated_at": None,
        }
        self.rows["t1"] = rec
        return rec

    async def get(self, thread_id):
        return self.rows.get(thread_id)

    async def rename(self, thread_id, title):
        self.rows[thread_id]["title"] = title

    async def delete(self, thread_id):
        self.rows.pop(thread_id, None)

    async def touch(self, thread_id):
        pass


class FakePrefs:
    async def get(self, user_id, namespace):
        return {}

    async def set(self, user_id, namespace, key, value):
        pass


@pytest.fixture
def client(monkeypatch):
    async def fake_discover(_meta, _backend):
        return [], []

    monkeypatch.setattr(skills_mod, "discover_skills", fake_discover)
    monkeypatch.setattr(tools_mod, "load_mcp_tools", lambda _names, _cfg: [])

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        build_resource_router(
            meta=SimpleNamespace(skills_map={}, mcp_servers_config={}),
            thread_store=FakeThreadStore(),
            prefs_store=FakePrefs(),
            backend=object(),
            user_id_dependency=lambda: "u1",
        )
    )
    return TestClient(app)


def test_all_resource_routes_mounted(client):
    assert client.get("/threads").status_code == 200
    assert client.get("/skills").status_code == 200
    assert client.get("/tools").status_code == 200
    assert client.get("/mcp-servers").status_code == 200


def test_unknown_thread_maps_to_404(client):
    assert client.patch("/threads/nope", json={"title": "x"}).status_code == 404
