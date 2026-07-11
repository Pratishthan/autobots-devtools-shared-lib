# ABOUTME: Pure reducer projecting AG-UI events into the AMA activity-rail shape.
# ABOUTME: Derives activity[]{dot,glow,title,mono,sub,isRunning} + stats{tokens,tools,latency}.

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from autobots_devtools_shared_lib.dynagent.ui.stream_attribution import StreamAttribution

_INFO = "var(--info)"  # sub-agent dot
_ACCENT = "var(--accent)"  # main-agent tool dot


def _short(name: str) -> str:
    """Strip the '<server>__' MCP prefix for display."""
    return name.split("__", 1)[1] if "__" in name else name


def _run_id(parent_message_id: str | None) -> str | None:
    if not parent_message_id:
        return None
    return parent_message_id.removeprefix("lc_run--")


def _format_sub(running: bool, ms: int | None, tokens: int | None) -> str:
    if running:
        return "running"
    parts = ["completed"]
    if ms is not None:
        parts.append(f"{ms}ms")
    if tokens:
        parts.append(f"{tokens} tok")
    return " · ".join(parts)


def _find_tool_call_id(output: Any) -> str | None:
    """Recursively find a ToolMessage's tool_call_id in a RAW on_tool_end output."""
    if isinstance(output, dict):
        tcid = output.get("tool_call_id")
        if isinstance(tcid, str):
            return tcid
        for value in output.values():
            found = _find_tool_call_id(value)
            if found:
                return found
    elif isinstance(output, list):
        for value in output:
            found = _find_tool_call_id(value)
            if found:
                return found
    return None


@dataclass
class _Tool:
    name: str
    parent_run_id: str | None
    start_ms: int | None
    end_ms: int | None = None
    running: bool = True
    subagent_type: str | None = None
    args_buf: list[str] = field(default_factory=list)


class ActivityProjection:
    """Reduce AG-UI events into the README's activity-rail + telemetry-footer shape."""

    def __init__(self, mcp_servers: set[str], main_agent_name: str | None = None):
        self._mcp_servers = mcp_servers
        self._main_agent_name = main_agent_name
        self._first_agent: str | None = None
        self._run_agent: dict[str, str] = {}  # run_id -> lc_agent_name
        self._attr = StreamAttribution()
        self._model_dispatch: dict[str, str] = {}  # subagent model run_id -> dispatch run_id
        self._toolu_dispatch: dict[str, str] = {}  # AG-UI toolu id -> dispatch run_id
        self._tools: dict[str, _Tool] = {}  # tool_call_id -> _Tool
        self._order: list[str] = []  # tool_call_id in start order
        self._tokens: dict[str, int] = {}  # agent name -> summed total_tokens
        self._tool_count = 0
        self._run_start_ms: int | None = None
        self._run_end_ms: int | None = None
        self.dirty = False

    # ── ingestion ────────────────────────────────────────────────────────────
    def observe(self, event: dict[str, Any]) -> None:
        etype = event.get("type")
        if etype == "RUN_STARTED":
            self._run_start_ms = event.get("_t_ms")
        elif etype == "RUN_FINISHED":
            self._run_end_ms = event.get("_t_ms")
            self.dirty = True
        elif etype == "RAW":
            self._observe_raw(event.get("event") or {})
        elif etype == "TOOL_CALL_START":
            tcid = event["tool_call_id"]
            self._tools[tcid] = _Tool(
                name=event["tool_call_name"],
                parent_run_id=_run_id(event.get("parent_message_id")),
                start_ms=event.get("_t_ms"),
            )
            self._order.append(tcid)
            self._tool_count += 1
            self.dirty = True
        elif etype == "TOOL_CALL_ARGS":
            tool = self._tools.get(event["tool_call_id"])
            if tool is not None:
                tool.args_buf.append(event.get("delta") or "")
        elif etype == "TOOL_CALL_END":
            tool = self._tools.get(event["tool_call_id"])
            if tool is not None and tool.name == "task":
                try:
                    parsed = json.loads("".join(tool.args_buf) or "{}")
                    tool.subagent_type = parsed.get("subagent_type")
                except json.JSONDecodeError:
                    tool.subagent_type = None
            self.dirty = True
        elif etype == "TOOL_CALL_RESULT":
            tcid = event.get("tool_call_id")
            if isinstance(tcid, str):
                tool = self._tools.get(tcid)
                if tool is not None:
                    tool.running = False
                    tool.end_ms = event.get("_t_ms")
                    self.dirty = True

    def _observe_raw(self, raw: dict[str, Any]) -> None:
        self._attr.observe(raw)
        name = str(raw.get("event") or "")

        if name == "on_tool_end" and raw.get("name") == "task":
            self._record_toolu_dispatch(raw)
            return

        if not name.startswith("on_chat_model"):
            return
        run_id = raw.get("run_id")
        agent = (raw.get("metadata") or {}).get("lc_agent_name")
        if run_id and agent:
            self._run_agent[run_id] = agent
            if self._first_agent is None:
                self._first_agent = agent
        dispatch = self._attr.dispatch_of(raw)
        if run_id and dispatch:
            self._model_dispatch[run_id] = dispatch
        if name == "on_chat_model_end" and agent:
            usage = ((raw.get("data") or {}).get("output") or {}).get("usage_metadata")
            if usage:
                self._tokens[agent] = self._tokens.get(agent, 0) + usage.get("total_tokens", 0)
                self.dirty = True

    def _record_toolu_dispatch(self, raw: dict[str, Any]) -> None:
        """Bridge the AG-UI toolu id to the RAW dispatch run_id via the task's ToolMessage."""
        dispatch = raw.get("run_id")
        if not dispatch:
            return
        data = raw.get("data")
        toolu = _find_tool_call_id(data.get("output") if isinstance(data, dict) else None)
        if toolu:
            self._toolu_dispatch[toolu] = dispatch

    # ── projection ───────────────────────────────────────────────────────────
    def _main_agent(self) -> str | None:
        return self._main_agent_name or self._first_agent

    def _is_mcp(self, name: str) -> bool:
        return any(name.startswith(f"{server}__") for server in self._mcp_servers)

    def _nested_mono(self, dispatch_id: str | None) -> str:
        """Summarise a sub-agent dispatch's own tool calls into a mono chip."""
        if dispatch_id is None:
            return ""
        nested = [
            t
            for t in self._tools.values()
            if t.name != "task" and self._model_dispatch.get(t.parent_run_id or "") == dispatch_id
        ]
        if not nested:
            return ""
        mcp = next((t for t in nested if self._is_mcp(t.name)), None)
        chosen = mcp or nested[0]
        return f"MCP {_short(chosen.name)}" if self._is_mcp(chosen.name) else _short(chosen.name)

    def snapshot(self) -> dict[str, Any]:
        main = self._main_agent()
        activity: list[dict] = []
        for tcid in self._order:
            tool = self._tools[tcid]
            ms = (
                tool.end_ms - tool.start_ms
                if tool.end_ms is not None and tool.start_ms is not None
                else None
            )
            if tool.name == "task":
                dispatch_id = self._toolu_dispatch.get(tcid)
                if dispatch_id is not None:
                    title = self._attr.dispatch_label(dispatch_id)
                else:
                    title = tool.subagent_type or "sub-agent"
                activity.append(
                    {
                        "dot": _INFO,
                        "glow": tool.running,
                        "title": title,
                        "mono": self._nested_mono(dispatch_id),
                        "sub": _format_sub(
                            tool.running, ms, self._tokens.get(tool.subagent_type or "")
                        ),
                        "isRunning": tool.running,
                    }
                )
                continue
            origin = self._run_agent.get(tool.parent_run_id or "", main)
            if origin != main:
                continue  # nested sub-agent tool call, folded into its task item
            is_mcp = self._is_mcp(tool.name)
            activity.append(
                {
                    "dot": _ACCENT,
                    "glow": tool.running,
                    "title": _short(tool.name),
                    "mono": f"MCP {_short(tool.name)}" if is_mcp else _short(tool.name),
                    "sub": _format_sub(tool.running, ms, None),
                    "isRunning": tool.running,
                }
            )
        latency = (
            self._run_end_ms - self._run_start_ms
            if self._run_end_ms is not None and self._run_start_ms is not None
            else None
        )
        stats = {
            "tokens": sum(self._tokens.values()),
            "tools": self._tool_count,
            "latency": latency,
        }
        return {"activity": activity, "stats": stats}


def project_events(
    events: Iterable[dict[str, Any]], mcp_servers: set[str], main_agent_name: str | None = None
) -> dict[str, Any]:
    """Convenience: run the reducer over all events and return the final snapshot."""
    proj = ActivityProjection(mcp_servers, main_agent_name)
    for event in events:
        proj.observe(event)
    return proj.snapshot()
