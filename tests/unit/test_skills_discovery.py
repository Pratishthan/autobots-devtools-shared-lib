# ABOUTME: Unit tests for discover_skills mapping, last-wins dedupe, and warnings.
# ABOUTME: Monkeypatches deepagents' _alist_skills_with_errors — no real backend needed.

from types import SimpleNamespace

import pytest


def _skill(name, desc, category=None):
    return {
        "name": name,
        "description": desc,
        "path": f"/skills/{name}/SKILL.md",
        "metadata": {"category": category} if category else {},
        "license": None,
        "compatibility": None,
        "allowed_tools": [],
    }


@pytest.mark.asyncio
async def test_maps_and_dedupes_last_wins(monkeypatch):
    import autobots_devtools_shared_lib.dynagent.api.skills_discovery as mod

    async def fake_loader(_backend, source_path):
        if source_path == "/skills/base/":
            return [_skill("alpha", "old alpha", "core"), _skill("beta", "beta desc")], None
        return [_skill("alpha", "new alpha", "core")], None

    monkeypatch.setattr(mod, "_alist_skills_with_errors", fake_loader)

    meta = SimpleNamespace(skills_map={"assistant": ["/skills/base/", "/skills/user/"]})
    skills, warnings = await mod.discover_skills(meta, backend=object())

    by_name = {s["name"]: s for s in skills}
    assert by_name["alpha"]["description"] == "new alpha"  # last source wins
    assert by_name["alpha"]["category"] == "core"
    assert by_name["alpha"]["enabled"] is True
    assert by_name["beta"]["category"] is None
    assert warnings == []


@pytest.mark.asyncio
async def test_aggregates_source_warnings(monkeypatch):
    import autobots_devtools_shared_lib.dynagent.api.skills_discovery as mod

    async def fake_loader(_backend, source_path):
        return [], f"Cannot load skills from '{source_path}': boom"

    monkeypatch.setattr(mod, "_alist_skills_with_errors", fake_loader)
    meta = SimpleNamespace(skills_map={"assistant": ["/skills/"]})
    skills, warnings = await mod.discover_skills(meta, backend=object())

    assert skills == []
    assert warnings == ["Cannot load skills from '/skills/': boom"]


@pytest.mark.asyncio
async def test_dedupes_source_paths_across_roster(monkeypatch):
    import autobots_devtools_shared_lib.dynagent.api.skills_discovery as mod

    seen: list[str] = []

    async def fake_loader(_backend, source_path):
        seen.append(source_path)
        return [], None

    monkeypatch.setattr(mod, "_alist_skills_with_errors", fake_loader)
    meta = SimpleNamespace(skills_map={"assistant": ["/skills/"], "wiring-check": ["/skills/"]})
    await mod.discover_skills(meta, backend=object())
    assert seen == ["/skills/"]  # deduped, loaded once
