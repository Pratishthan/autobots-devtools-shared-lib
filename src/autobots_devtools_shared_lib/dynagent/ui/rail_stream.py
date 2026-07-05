# ABOUTME: Streams the derived AMA activity rail alongside the AG-UI event stream.
# ABOUTME: Wraps LangGraphAGUIAgent.run, injecting non-destructive STATE_DELTA updates.

import time
from collections.abc import AsyncIterator

from ag_ui.core import EventType, StateDeltaEvent
from copilotkit import LangGraphAGUIAgent

from autobots_devtools_shared_lib.dynagent.ui.activity_projection import ActivityProjection


def _to_dict(event) -> dict:
    if isinstance(event, dict):
        return event
    return event.model_dump()


async def project_stream(
    inner: AsyncIterator,
    mcp_servers: set[str],
    main_agent_name: str | None = None,
) -> AsyncIterator:
    """Yield every event from `inner`; after each rail change, inject a STATE_DELTA.

    The delta is JSON Patch `add /activity` + `add /stats` — non-destructive, so it never
    clobbers the raw deepagents state keys (files/todos) already carried by STATE_SNAPSHOT.
    """
    proj = ActivityProjection(mcp_servers, main_agent_name)
    t0: float | None = None
    async for event in inner:
        data = _to_dict(event)
        now = time.monotonic() * 1000
        if t0 is None:
            t0 = now
        data.setdefault("_t_ms", int(now - t0))
        proj.observe(data)
        yield event
        if proj.dirty:
            proj.dirty = False
            snap = proj.snapshot()
            yield StateDeltaEvent(
                type=EventType.STATE_DELTA,
                delta=[
                    {"op": "add", "path": "/activity", "value": snap["activity"]},
                    {"op": "add", "path": "/stats", "value": snap["stats"]},
                ],
            )


class RailAGUIAgent(LangGraphAGUIAgent):
    """LangGraphAGUIAgent that streams the derived activity rail via STATE_DELTA."""

    def __init__(
        self,
        *args,
        mcp_servers: set[str] | None = None,
        main_agent_name: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._mcp_servers = mcp_servers or set()
        self._main_agent_name = main_agent_name

    async def run(self, input):  # matches LangGraphAGUIAgent's base signature (self, input)
        async for event in project_stream(
            super().run(input), self._mcp_servers, self._main_agent_name
        ):
            yield event
