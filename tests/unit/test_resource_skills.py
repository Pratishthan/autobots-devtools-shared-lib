# ABOUTME: TestClient coverage for the /skills router: list merged with prefs + PATCH.
# ABOUTME: discover_skills is monkeypatched; a dict-backed PrefsStore drives enabled state.

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import autobots_devtools_shared_lib.dynagent.api.resources.skills as skills_mod
from autobots_devtools_shared_lib.dynagent.api.resources.skills import build_skills_router


class FakePrefs:
    def __init__(self) -> None:
        self.kv: dict[tuple[str, str, str], bool] = {}

    async def get(self, user_id, namespace):
        return {k[2]: v for k, v in self.kv.items() if k[0] == user_id and k[1] == namespace}

    async def set(self, user_id, namespace, key, value):
        self.kv[(user_id, namespace, key)] = value


@pytest.fixture
def prefs():
    return FakePrefs()


@pytest.fixture
def client(monkeypatch, prefs):
    async def fake_discover(_meta, _backend):
        return (
            [
                {
                    "name": "web-research",
                    "description": "research",
                    "category": "core",
                    "enabled": True,
                },
                {"name": "demo-fact", "description": "facts", "category": None, "enabled": True},
            ],
            ["a warning"],
        )

    monkeypatch.setattr(skills_mod, "discover_skills", fake_discover)
    app = FastAPI()
    app.include_router(
        build_skills_router(
            meta=SimpleNamespace(skills_map={}),
            backend=object(),
            prefs_store=prefs,
            user_id_dependency=lambda: "u1",
        )
    )
    return TestClient(app)


def test_list_skills_returns_skills_and_warnings(client):
    body = client.get("/skills").json()
    names = {s["name"] for s in body["skills"]}
    assert names == {"web-research", "demo-fact"}
    assert body["warnings"] == ["a warning"]
    assert all(s["enabled"] for s in body["skills"])


def test_pref_disables_skill(client, prefs):
    prefs.kv[("u1", "skills", "demo-fact")] = False
    body = client.get("/skills").json()
    by_name = {s["name"]: s for s in body["skills"]}
    assert by_name["demo-fact"]["enabled"] is False
    assert by_name["web-research"]["enabled"] is True


def test_patch_sets_pref(client, prefs):
    resp = client.patch("/skills/demo-fact", json={"enabled": False})
    assert resp.status_code == 200
    assert prefs.kv[("u1", "skills", "demo-fact")] is False
