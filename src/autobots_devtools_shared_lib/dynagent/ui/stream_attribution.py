# ABOUTME: Pure reducer attributing raw astream_events to their owning lc_agent_name.
# ABOUTME: Mirrors ActivityProjection's _run_agent map + _first_agent heuristic; no Chainlit dep.

from dataclasses import dataclass
from typing import Any

_LABEL_DESC_MAX = 60


@dataclass
class DispatchInfo:
    """What a `task` dispatch launched: its subagent type and task description."""

    subagent_type: str | None
    description: str | None


def _agent_of(event: dict[str, Any]) -> str | None:
    return (event.get("metadata") or {}).get("lc_agent_name")


def _is_chat_model(event: dict[str, Any]) -> bool:
    return str(event.get("event") or "").startswith("on_chat_model")


def _trim_description(description: str | None) -> str | None:
    if not description:
        return None
    collapsed = " ".join(description.split())
    if len(collapsed) <= _LABEL_DESC_MAX:
        return collapsed
    cut = collapsed[:_LABEL_DESC_MAX].rsplit(" ", 1)[0] or collapsed[:_LABEL_DESC_MAX]
    return f"{cut}…"


class StreamAttribution:
    """Answer 'which agent / which dispatch owns this event?' for a single agent run."""

    def __init__(self) -> None:
        self.run_agent: dict[str, str] = {}
        self.main_agent: str | None = None
        self.dispatches: dict[str, DispatchInfo] = {}

    def observe(self, event: dict[str, Any]) -> None:
        """Ingest one raw astream_events dict. Call once per event before querying."""
        agent = _agent_of(event)
        run_id = event.get("run_id")
        if agent and run_id:
            self.run_agent[run_id] = agent
        if agent and self.main_agent is None and _is_chat_model(event):
            self.main_agent = agent
        self._observe_task_start(event)

    def _observe_task_start(self, event: dict[str, Any]) -> None:
        if not self.is_task_dispatch(event):
            return
        run_id = event.get("run_id")
        if not run_id:
            return
        tool_input = event.get("data", {}).get("input")
        if isinstance(tool_input, dict):
            info = DispatchInfo(tool_input.get("subagent_type"), tool_input.get("description"))
        else:
            info = DispatchInfo(None, None)
        self.dispatches[run_id] = info

    def owner(self, event: dict[str, Any]) -> str | None:
        """The lc_agent_name owning this event; falls back to the run_agent map."""
        agent = _agent_of(event)
        if agent:
            return agent
        run_id = event.get("run_id")
        return self.run_agent.get(run_id) if run_id else None

    def is_main(self, agent: str | None) -> bool:
        """True for the main/coordinator agent, or when attribution is unknown (fail-open)."""
        return agent is None or agent == self.main_agent

    def dispatch_of(self, event: dict[str, Any]) -> str | None:
        """Nearest registered task run_id in event['parent_ids'] (root->parent ordered)."""
        for run_id in reversed(event.get("parent_ids") or []):
            if run_id in self.dispatches:
                return run_id
        return None

    def dispatch_label(self, run_id: str) -> str:
        info = self.dispatches.get(run_id)
        subagent_type = info.subagent_type if info else None
        description = _trim_description(info.description) if info else None
        if subagent_type and description:
            return f"{subagent_type} · {description}"
        if subagent_type:
            return subagent_type
        return "sub-agent"

    def subagent_key(self, event: dict[str, Any]) -> str | None:
        """Identity of the subagent surface this event belongs to.

        Dispatch run_id when a task ancestor is known (separates same-type fan-out),
        else the distinct lc_agent_name (legacy fallback for streams without parent_ids),
        else None (main agent / fail-open).
        """
        dispatch = self.dispatch_of(event)
        if dispatch is not None:
            return dispatch
        agent = self.owner(event)
        if agent is not None and agent != self.main_agent:
            return agent
        return None

    def step_label(self, key: str) -> str:
        """dispatch_label(key) for a known dispatch run_id, else the bare key."""
        if key in self.dispatches:
            return self.dispatch_label(key)
        return key

    @staticmethod
    def is_task_dispatch(event: dict[str, Any]) -> bool:
        """True when this on_tool_start is a deepagents `task` subagent dispatch."""
        return event.get("event") == "on_tool_start" and event.get("name") == "task"
