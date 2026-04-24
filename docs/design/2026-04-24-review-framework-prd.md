# PRD — Human Review Framework for Dynagent

**Date:** 2026-04-24
**Repo:** `autobots-devtools-shared-lib`
**Status:** Draft

## Problem

Dynagent apps increasingly run agent pipelines that produce artifacts (code, docs, configs) destined for downstream systems — git repos, Jira tickets, deployment pipelines. Today each app that wants a human-in-the-loop review before those artifacts leave the sandbox has to build its own review UI, routing, and state handling. There is no shared primitive for "pause the pipeline, let a human review grouped per-agent changes, route feedback back to the producing agent."

This PRD proposes a review framework in the shared library that any Dynagent app (MER, Jarvis, Pay) can adopt by supplying a small amount of app-specific glue.

## Goals

- Standard on-disk review payload schema.
- Generic write-tool audit mechanism that tags file writes with the producing agent.
- Chainlit custom element that renders a PR-style grouped review UI purely from the payload.
- Orchestrator that re-invokes the owning agent with cumulative feedback when a group is rejected.
- Notifier helper for async "review ready" pings (Slack/email).
- Zero knowledge of any specific app (Jarvis). No imports from app packages.

## Non-Goals

- App-specific slash commands (e.g., commit-push, Jenkins triggers) — those belong to apps.
- App-specific state fields (JIRA ids, repo names) — apps extend `Dynagent` state.
- Line-level inline comments, syntax-highlighted diffs, per-agent commits — future work.
- Auto-rerun of downstream agents when upstream re-runs — apps may layer this themselves.

## Scope

### 1. Review Payload (`dynagent.review.payload`)

Canonical JSON schema and loader.

```json
{
  "status": "awaiting_review | approved | changes_requested",
  "pipeline_order": ["agent-a", "agent-b", ...],
  "suppressed_globs": ["glob/**"],
  "groups": [
    {
      "agent": "agent-a",
      "agent_display": "Agent A",
      "summary": "...",
      "files": [{"path": "...", "status": "added|modified|deleted",
                 "diff": "...", "suppressed": false}],
      "review_state": "pending | approved | changes_requested",
      "upstream_stale": false
    }
  ],
  "history": [{"ts": "...", "agent": "...", "action": "...", "feedback": "..."}],
  "app": {}
}
```

- `app` is a free-form object reserved for app-specific metadata (Jira id, repo, build url, workspace id, etc.). Shared lib never inspects it.
- Helpers: `load_payload(path)`, `save_payload(path, payload)`, `apply_suppression(payload)`, `compute_upstream_stale(payload)`.

### 2. Write-Tool Audit (`dynagent.review.audit`)

A decorator / wrapper for any file-write tool:

```python
from dynagent.review.audit import audit_writes

@audit_writes(payload_path_from=lambda rt: rt.state["review_payload_path"])
@tool
def my_write_file(runtime: ToolRuntime[None, Dynagent], path: str, content: str) -> str:
    ...
```

Behavior:

- Reads `calling_agent` from `ToolRuntime` state (Dynagent sets this today).
- On successful write, upserts into `payload.groups[calling_agent].files`, last-writer-wins on path.
- Captures a diff snippet if a prior version exists.

Agnostic to the underlying write target (fserver, local disk, S3) — the decorator only observes the call.

### 3. Review Orchestrator (`dynagent.review.orchestrator`)

Owns the control loop: payload → human → agent re-invoke.

```python
ReviewOrchestrator(
    payload_path: str,
    agent_factory: Callable[[str], Agent],  # agent_name → runnable agent
    on_approve_all: Callable[[ReviewPayload], Awaitable[None]],
    on_notify_ready: Callable[[str], None] | None = None,   # deep_link → send
    poll_interval_s: float = 2.0,
)
```

Responsibilities:

- Watch payload for `status` / `group.review_state` transitions.
- On a group flipping to `changes_requested`: re-invoke `agent_factory(agent)` with the `history` entries for that agent + original input context; flip `review_state` back to `pending`; mark downstream groups `upstream_stale = true`.
- On top-level `approved`: call `on_approve_all(payload)`.
- On first arrival at `awaiting_review`: call `on_notify_ready(deep_link)` once.

### 4. Chainlit Review Element (`dynagent.ui.review_element`)

Chainlit custom element (React component + Python shim). Parallels the existing `dynagent.ui.stream_agent_events`.

- Input: payload path (or payload dict).
- Renders grouped cards, per-group Approve / Request-changes, collapsible diff viewer, top-level Approve-all button (enabled only when all non-suppressed groups are `approved` and none are `upstream_stale`).
- Actions write payload mutations via a callback supplied by the app:

```python
review_element(
    payload_path: str,
    on_mutation: Callable[[ReviewPayload], None],
)
```

- Renderer is stateless: every render is a pure function of payload.

### 5. Notifier (`dynagent.notify`)

```python
def notify(channel: NotifyChannel, message: str) -> None: ...
```

- Channels: `slack` (webhook URL from env), `email` (SMTP from env), `none` (no-op).
- Failures logged, not raised.
- Used by app-level glue; orchestrator accepts `on_notify_ready` which a typical app wires to this helper.

## Public API Summary

```python
from dynagent.review import (
    ReviewPayload, load_payload, save_payload,
    audit_writes,
    ReviewOrchestrator,
)
from dynagent.ui import review_element
from dynagent.notify import notify, NotifyChannel
```

## Boundary Rules

- Shared lib MUST NOT import from any app package.
- Shared lib does not own slash commands. App wires `on_approve_all` to its own command.
- Payload `app` field is opaque — shared lib never reads or validates it.
- Suppressed globs and pipeline order are parameters; no defaults.

## Success Criteria

- Use case adopts the framework using only config + ~1 orchestrator wiring call (see Use case PRD).
- A second app (e.g., Jarvis) can adopt with no changes to shared lib.
- `ReviewPayload` round-trips through `load_payload` / `save_payload` without loss.
- Chainlit element renders any valid payload; unknown `app` fields do not break rendering.
- Orchestrator unit tests cover: approve group, request changes, upstream stale propagation, approve-all fires hook, notify-ready fires exactly once.

## Open Questions

- Transport for payload watch: filesystem polling (portable) vs Redis pub/sub (faster). Default to polling in v1; add pub/sub adapter later.
- Concurrent editors on the same payload: last-writer-wins for v1; add `payload.version` optimistic lock if collisions show up in practice.
- Versioning: include `schema_version` in payload so future lib upgrades can migrate.
