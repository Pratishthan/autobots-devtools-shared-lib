# ABOUTME: Live skills discovery for /skills — wraps deepagents' own loader.
# ABOUTME: Calls the loader live (not off checkpoint state) to sidestep durable staleness.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from deepagents.middleware.skills import _alist_skills_with_errors

from autobots_devtools_shared_lib.common.observability import get_logger

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.dynagent.agents.agent_meta import AgentMeta

logger = get_logger(__name__)


class SkillInfo(TypedDict):
    """One skill as surfaced to the left rail. `enabled` is a UI pref, merged later."""

    name: str
    description: str
    category: str | None
    enabled: bool


def _ordered_unique_sources(meta: AgentMeta) -> list[str]:
    """Union every source path across the roster, preserving first-seen order."""
    seen: list[str] = []
    for sources in meta.skills_map.values():
        for source_path in sources:
            if source_path not in seen:
                seen.append(source_path)
    return seen


async def discover_skills(meta: AgentMeta, backend: Any) -> tuple[list[SkillInfo], list[str]]:
    """Load skills live via deepagents' loader, deduped last-wins, with warnings.

    Isolated behind this helper so a future swap to a public deepagents API is one line.
    """
    by_name: dict[str, SkillInfo] = {}
    warnings: list[str] = []
    for source_path in _ordered_unique_sources(meta):
        try:
            found, source_error = await _alist_skills_with_errors(backend, source_path)
        except Exception as exc:  # degrade, never 500
            logger.warning("skills discovery failed for %s: %s", source_path, exc)
            warnings.append(f"Cannot load skills from '{source_path}': {exc}")
            continue
        if source_error is not None:
            warnings.append(source_error)
        for skill in found:
            by_name[skill["name"]] = SkillInfo(
                name=skill["name"],
                description=skill["description"],
                category=(skill.get("metadata") or {}).get("category"),
                enabled=True,
            )
    return list(by_name.values()), warnings
