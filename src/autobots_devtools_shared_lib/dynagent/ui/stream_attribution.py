# ABOUTME: Pure reducer attributing raw astream_events to their owning lc_agent_name.
# ABOUTME: Mirrors ActivityProjection's _run_agent map + _first_agent heuristic; no Chainlit dep.

from typing import Any


def _agent_of(event: dict[str, Any]) -> str | None:
    return (event.get("metadata") or {}).get("lc_agent_name")


def _is_chat_model(event: dict[str, Any]) -> bool:
    return str(event.get("event") or "").startswith("on_chat_model")


class StreamAttribution:
    """Answer 'which agent owns this event?' for a single agent run.

    Keeps two pieces of per-call state:
      - run_agent: run_id -> lc_agent_name, populated from every event that carries it.
      - main_agent: the first lc_agent_name seen on a chat-model event (the proven
        ActivityProjection._first_agent heuristic).
    """

    def __init__(self) -> None:
        self.run_agent: dict[str, str] = {}
        self.main_agent: str | None = None

    def observe(self, event: dict[str, Any]) -> None:
        """Ingest one raw astream_events dict. Call once per event before querying."""
        agent = _agent_of(event)
        run_id = event.get("run_id")
        if agent and run_id:
            self.run_agent[run_id] = agent
        if agent and self.main_agent is None and _is_chat_model(event):
            self.main_agent = agent

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

    @staticmethod
    def is_task_dispatch(event: dict[str, Any]) -> bool:
        """True when this on_tool_start is a deepagents `task` subagent dispatch."""
        return event.get("event") == "on_tool_start" and event.get("name") == "task"
