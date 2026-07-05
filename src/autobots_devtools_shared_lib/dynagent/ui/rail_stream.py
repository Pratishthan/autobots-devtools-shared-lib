# ABOUTME: Streams the derived AMA activity rail alongside the AG-UI event stream.
# ABOUTME: Wraps LangGraphAGUIAgent.run, injecting non-destructive STATE_DELTA updates.

import time
from collections.abc import AsyncIterator, Awaitable, Callable

from ag_ui.core import EventType, StateDeltaEvent
from copilotkit import LangGraphAGUIAgent

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.ui.activity_projection import ActivityProjection

logger = get_logger(__name__)


def _to_dict(event) -> dict:
    if isinstance(event, dict):
        return event
    return event.model_dump()


async def project_stream(
    inner: AsyncIterator,
    mcp_servers: set[str],
    main_agent_name: str | None = None,
    on_run_finished: Callable[[str], Awaitable[None]] | None = None,
) -> AsyncIterator:
    """Yield every event from `inner`; after each rail change, inject a STATE_DELTA.

    The delta is JSON Patch `add /activity` + `add /stats` — non-destructive, so it never
    clobbers the raw deepagents state keys (files/todos) already carried by STATE_SNAPSHOT.

    Projection is best-effort: any failure inside observe/snapshot drops the rail delta but
    never interrupts the underlying token stream. When `on_run_finished` is supplied it is
    invoked (best-effort) with the run's thread_id on RUN_FINISHED — the sole write-back
    from the streaming plane into the ThreadStore (touch()).
    """
    proj = ActivityProjection(mcp_servers, main_agent_name)
    t0: float | None = None

    def _flush_delta() -> StateDeltaEvent | None:
        """Consume any pending rail change and materialise it as a STATE_DELTA."""
        if not proj.dirty:
            return None
        proj.dirty = False
        try:
            snap = proj.snapshot()
        except Exception:
            logger.warning("activity projection snapshot failed; dropping delta", exc_info=True)
            return None
        return StateDeltaEvent(
            type=EventType.STATE_DELTA,
            delta=[
                {"op": "add", "path": "/activity", "value": snap["activity"]},
                {"op": "add", "path": "/stats", "value": snap["stats"]},
            ],
        )

    async for event in inner:
        data = _to_dict(event)
        now = time.monotonic() * 1000
        if t0 is None:
            t0 = now
        data.setdefault("_t_ms", int(now - t0))
        try:
            proj.observe(data)
        except Exception:
            logger.warning("activity projection observe failed; dropping delta", exc_info=True)
            proj.dirty = False

        # RUN_FINISHED is terminal: AG-UI rejects any event after it, so the final
        # rail delta (carrying end-of-run latency/stats) must be flushed *before* it.
        if data.get("type") == "RUN_FINISHED":
            delta = _flush_delta()
            if delta is not None:
                yield delta
            yield event
            if on_run_finished is not None:
                thread_id = data.get("thread_id")
                if thread_id:
                    try:
                        await on_run_finished(thread_id)
                    except Exception:
                        logger.warning("on_run_finished(touch) failed", exc_info=True)
            continue

        yield event
        delta = _flush_delta()
        if delta is not None:
            yield delta


class RailAGUIAgent(LangGraphAGUIAgent):
    """LangGraphAGUIAgent that streams the derived activity rail via STATE_DELTA."""

    def __init__(
        self,
        *args,
        mcp_servers: set[str] | None = None,
        main_agent_name: str | None = None,
        on_run_finished: Callable[[str], Awaitable[None]] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._mcp_servers = mcp_servers or set()
        self._main_agent_name = main_agent_name
        self._on_run_finished = on_run_finished

    async def run(self, input):  # matches LangGraphAGUIAgent's base signature (self, input)
        async for event in project_stream(
            super().run(input),
            self._mcp_servers,
            self._main_agent_name,
            self._on_run_finished,
        ):
            yield event
