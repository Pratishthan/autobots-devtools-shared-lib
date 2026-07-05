# ABOUTME: /skills router — lists live-loaded skills merged with per-user enabled prefs.
# ABOUTME: PATCH sets a UI-only pref; it does NOT gate agent behavior this cycle.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from autobots_devtools_shared_lib.dynagent.api.skills_discovery import discover_skills

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.dynagent.api.thread_store import PrefsStore

_NAMESPACE = "skills"


class _EnabledBody(BaseModel):
    enabled: bool


def build_skills_router(
    meta: Any,
    backend: Any,
    prefs_store: PrefsStore,
    user_id_dependency: Any,
) -> APIRouter:
    """Build the /skills router (list + enable/disable pref)."""
    router = APIRouter(prefix="/skills", tags=["skills"])

    @router.get("")
    async def list_skills(user_id: str = Depends(user_id_dependency)) -> dict[str, Any]:
        skills, warnings = await discover_skills(meta, backend)
        prefs = await prefs_store.get(user_id, _NAMESPACE)
        merged = [{**s, "enabled": prefs.get(s["name"], s["enabled"])} for s in skills]
        return {"skills": merged, "warnings": warnings}

    @router.patch("/{name}")
    async def set_skill_enabled(
        name: str, body: _EnabledBody, user_id: str = Depends(user_id_dependency)
    ) -> dict[str, bool]:
        await prefs_store.set(user_id, _NAMESPACE, name, body.enabled)
        return {"ok": True}

    return router
