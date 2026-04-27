# Review Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Dynagent review framework — payload schema, write-audit decorator, orchestrator, Chainlit review element, notifier — that any app can adopt with only app-specific glue.

**Architecture:** Pure-data payload as the coordination surface; write-tool decorator populates it; orchestrator watches it and re-invokes agents; Chainlit element renders it; notifier is an independent helper. Zero imports from app packages.

**Tech Stack:** Python 3.12, Pydantic, pytest (asyncio-auto), Chainlit custom elements (React + Python shim), LangGraph `ToolRuntime`.

**Spec:** `docs/design/2026-04-24-review-framework-prd.md`

---

## File Structure

New files under `src/autobots_devtools_shared_lib/`:

```
dynagent/review/__init__.py             # Public API re-exports
dynagent/review/payload.py              # Pydantic models + load/save + suppression + stale computation
dynagent/review/audit.py                # @audit_writes decorator
dynagent/review/orchestrator.py         # ReviewOrchestrator control loop
dynagent/ui/review_element/__init__.py  # Python shim
dynagent/ui/review_element/element.py   # cl.CustomElement binding
dynagent/ui/review_element/public/      # React component build output
dynagent/ui/review_element/src/         # React source
notify/__init__.py                      # notify(), NotifyChannel, env config
```

Tests:

```
tests/unit/review/__init__.py
tests/unit/review/test_payload.py
tests/unit/review/test_audit.py
tests/unit/review/test_orchestrator.py
tests/unit/test_notify.py
tests/integration/review/test_review_element.py   # Chainlit element smoke test
```

Each file has one responsibility. Payload is pure data. Audit only observes writes. Orchestrator only reacts to payload diffs. Element only renders. Notifier only sends.

---

## Task 0: Spike — verify `calling_agent` availability

**Purpose:** Confirm the audit decorator can read the producing agent from `ToolRuntime` without app cooperation. If not, bubble up a design change before writing tests.

**Files:**
- Read: `src/autobots_devtools_shared_lib/dynagent/services/structured_converter.py`
- Read: `src/autobots_devtools_shared_lib/dynagent/tools/state_tools.py`
- Read: `src/autobots_devtools_shared_lib/dynagent/agents/**` (entry points)

- [ ] **Step 1: Grep for where Dynagent sets or exposes the current agent name**

```bash
rg "current_agent|calling_agent|agent_name" src/autobots_devtools_shared_lib/dynagent/ -n
```

- [ ] **Step 2: Trace one tool invocation path**

Confirm: at `@tool` call time, can we read current agent name from `runtime.state`, `runtime.metadata`, or a context var?

- [ ] **Step 3: Document findings inline in the plan**

If `calling_agent` is already present: good, proceed.
If absent: add a prerequisite task to Dynagent core to plumb `current_agent` into `ToolRuntime.state` before each agent step. This must land before Task 2 starts.

- [ ] **Step 4: Commit findings (if any plan edits made)**

```bash
git add docs/superpowers/plans/2026-04-24-review-framework.md
git commit -m "plan: record calling_agent spike findings"
```

---

## Task 1: Payload module (TDD)

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/review/__init__.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/review/payload.py`
- Create: `tests/unit/review/__init__.py`
- Create: `tests/unit/review/test_payload.py`

### 1a. Pydantic models + round-trip

- [ ] **Step 1: Write failing round-trip test**

```python
# tests/unit/review/test_payload.py
from pathlib import Path
from autobots_devtools_shared_lib.dynagent.review.payload import (
    ReviewPayload, FileChange, GroupReview, HistoryEntry,
    load_payload, save_payload,
)

def test_round_trip_empty_payload(tmp_path: Path):
    p = tmp_path / "payload.json"
    payload = ReviewPayload(
        status="awaiting_review",
        pipeline_order=["a", "b"],
        suppressed_globs=[],
        groups=[],
        history=[],
        app={},
    )
    save_payload(p, payload)
    loaded = load_payload(p)
    assert loaded == payload

def test_round_trip_full_payload(tmp_path: Path):
    p = tmp_path / "payload.json"
    payload = ReviewPayload(
        status="awaiting_review",
        pipeline_order=["a", "b"],
        suppressed_globs=["gen/**"],
        groups=[
            GroupReview(
                agent="a", agent_display="A", summary="x",
                files=[FileChange(path="f.py", status="modified", diff="--- ...", suppressed=False)],
                review_state="pending", upstream_stale=False,
            )
        ],
        history=[HistoryEntry(ts="2026-04-24T00:00:00Z", agent="a", action="changes_requested", feedback="fix")],
        app={"jira": "X-1"},
    )
    save_payload(p, payload)
    assert load_payload(p) == payload
```

- [ ] **Step 2: Run tests, confirm FAIL**

```bash
pytest tests/unit/review/test_payload.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement minimal models + save/load**

```python
# src/autobots_devtools_shared_lib/dynagent/review/payload.py
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field

Status = Literal["awaiting_review", "approved", "changes_requested", "committed"]
ReviewState = Literal["pending", "approved", "changes_requested"]
FileStatus = Literal["added", "modified", "deleted"]

class FileChange(BaseModel):
    path: str
    status: FileStatus
    diff: str = ""
    suppressed: bool = False

class GroupReview(BaseModel):
    agent: str
    agent_display: str
    summary: str = ""
    files: list[FileChange] = Field(default_factory=list)
    review_state: ReviewState = "pending"
    upstream_stale: bool = False

class HistoryEntry(BaseModel):
    ts: str
    agent: str
    action: str
    feedback: str = ""

class ReviewPayload(BaseModel):
    schema_version: int = 1
    status: Status = "awaiting_review"
    pipeline_order: list[str] = Field(default_factory=list)
    suppressed_globs: list[str] = Field(default_factory=list)
    groups: list[GroupReview] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    app: dict[str, Any] = Field(default_factory=dict)

def load_payload(path: str | Path) -> ReviewPayload:
    return ReviewPayload.model_validate_json(Path(path).read_text())

def save_payload(path: str | Path, payload: ReviewPayload) -> None:
    Path(path).write_text(payload.model_dump_json(indent=2))
```

- [ ] **Step 4: Run tests, confirm PASS**

- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/dynagent/review tests/unit/review
git commit -m "feat(review): add payload schema with round-trip"
```

### 1b. Suppression filter

- [ ] **Step 1: Add failing tests**

```python
def test_apply_suppression_marks_matching_files():
    payload = ReviewPayload(
        suppressed_globs=["generated-src/**", "docs/agent-generator-meta/**"],
        groups=[GroupReview(agent="a", agent_display="A", files=[
            FileChange(path="generated-src/X.java", status="added"),
            FileChange(path="src/Real.java", status="modified"),
            FileChange(path="docs/agent-generator-meta/trace.json", status="added"),
        ])],
    )
    apply_suppression(payload)
    assert payload.groups[0].files[0].suppressed is True
    assert payload.groups[0].files[1].suppressed is False
    assert payload.groups[0].files[2].suppressed is True

def test_apply_suppression_idempotent():
    payload = ReviewPayload(suppressed_globs=["x/**"], groups=[
        GroupReview(agent="a", agent_display="A",
                    files=[FileChange(path="x/y.py", status="added", suppressed=True)])])
    apply_suppression(payload)
    apply_suppression(payload)
    assert payload.groups[0].files[0].suppressed is True
```

- [ ] **Step 2: Run, confirm FAIL**

- [ ] **Step 3: Implement**

```python
from fnmatch import fnmatch

def apply_suppression(payload: ReviewPayload) -> None:
    for group in payload.groups:
        for f in group.files:
            f.suppressed = any(fnmatch(f.path, g) for g in payload.suppressed_globs)
```

Note: Python's `fnmatch` handles `*` but not true `**` glob semantics. Use `pathlib.PurePath.match` or the `pathspec` lib if you need gitignore-style semantics. Start with `pathspec` (it's already a common dep):

```python
import pathspec

def apply_suppression(payload: ReviewPayload) -> None:
    spec = pathspec.PathSpec.from_lines("gitwildmatch", payload.suppressed_globs)
    for group in payload.groups:
        for f in group.files:
            f.suppressed = spec.match_file(f.path)
```

Add `pathspec` to `pyproject.toml` if absent.

- [ ] **Step 4: Run tests, confirm PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat(review): add glob-based suppression"
```

### 1c. Upstream stale computation

- [ ] **Step 1: Failing tests**

```python
def test_upstream_stale_marks_downstream_when_upstream_not_approved():
    payload = ReviewPayload(
        pipeline_order=["a", "b", "c"],
        groups=[
            GroupReview(agent="a", agent_display="A", review_state="changes_requested"),
            GroupReview(agent="b", agent_display="B", review_state="approved"),
            GroupReview(agent="c", agent_display="C", review_state="approved"),
        ],
    )
    compute_upstream_stale(payload)
    assert payload.groups[0].upstream_stale is False
    assert payload.groups[1].upstream_stale is True
    assert payload.groups[2].upstream_stale is True

def test_upstream_stale_clear_when_all_approved():
    payload = ReviewPayload(
        pipeline_order=["a", "b"],
        groups=[
            GroupReview(agent="a", agent_display="A", review_state="approved"),
            GroupReview(agent="b", agent_display="B", review_state="approved"),
        ],
    )
    compute_upstream_stale(payload)
    assert all(not g.upstream_stale for g in payload.groups)
```

- [ ] **Step 2: Confirm FAIL**
- [ ] **Step 3: Implement**

```python
def compute_upstream_stale(payload: ReviewPayload) -> None:
    order = {name: i for i, name in enumerate(payload.pipeline_order)}
    by_agent = {g.agent: g for g in payload.groups}
    for i, name in enumerate(payload.pipeline_order):
        g = by_agent.get(name)
        if not g:
            continue
        # Stale iff any earlier group is not approved (including pending, changes_requested).
        g.upstream_stale = any(
            (by_agent.get(earlier) and by_agent[earlier].review_state != "approved")
            for earlier in payload.pipeline_order[:i]
        )
```

- [ ] **Step 4: Confirm PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat(review): compute upstream_stale flags"
```

### 1d. `__init__.py` re-exports

- [ ] **Step 1: Write**

```python
# src/autobots_devtools_shared_lib/dynagent/review/__init__.py
from .payload import (
    FileChange, GroupReview, HistoryEntry, ReviewPayload,
    load_payload, save_payload, apply_suppression, compute_upstream_stale,
)

__all__ = [
    "FileChange", "GroupReview", "HistoryEntry", "ReviewPayload",
    "load_payload", "save_payload", "apply_suppression", "compute_upstream_stale",
]
```

- [ ] **Step 2: Commit**

---

## Task 2: Notifier module (TDD, independent)

**Files:**
- Create: `src/autobots_devtools_shared_lib/notify/__init__.py`
- Create: `tests/unit/test_notify.py`

- [ ] **Step 1: Failing tests**

```python
# tests/unit/test_notify.py
import pytest
from unittest.mock import patch
from autobots_devtools_shared_lib.notify import notify, NotifyChannel

def test_notify_none_is_noop(caplog):
    notify(channel="none", message="hi")
    assert "hi" not in caplog.text

def test_notify_slack_posts_to_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/x/y/z")
    with patch("autobots_devtools_shared_lib.notify.requests.post") as post:
        post.return_value.status_code = 200
        notify(channel="slack", message="review ready")
        post.assert_called_once()
        args, kwargs = post.call_args
        assert args[0] == "https://hooks.slack.com/services/x/y/z"
        assert kwargs["json"]["text"] == "review ready"

def test_notify_slack_missing_env_logs_warning(monkeypatch, caplog):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    notify(channel="slack", message="x")
    assert "SLACK_WEBHOOK_URL" in caplog.text

def test_notify_slack_http_failure_is_swallowed(monkeypatch, caplog):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    with patch("autobots_devtools_shared_lib.notify.requests.post", side_effect=Exception("boom")):
        notify(channel="slack", message="x")  # must not raise
    assert "boom" in caplog.text or "notify" in caplog.text.lower()

def test_notify_invalid_channel_raises():
    with pytest.raises(ValueError):
        notify(channel="carrier-pigeon", message="x")  # type: ignore
```

- [ ] **Step 2: Confirm FAIL**
- [ ] **Step 3: Implement**

```python
# src/autobots_devtools_shared_lib/notify/__init__.py
from __future__ import annotations
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Literal

import requests

logger = logging.getLogger(__name__)

NotifyChannel = Literal["slack", "email", "none"]

def notify(channel: NotifyChannel, message: str) -> None:
    if channel == "none":
        return
    if channel == "slack":
        _notify_slack(message)
        return
    if channel == "email":
        _notify_email(message)
        return
    raise ValueError(f"Unknown notify channel: {channel!r}")

def _notify_slack(message: str) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        logger.warning("notify(slack): SLACK_WEBHOOK_URL not set; skipping")
        return
    try:
        resp = requests.post(url, json={"text": message}, timeout=10)
        if resp.status_code >= 400:
            logger.warning("notify(slack): HTTP %s", resp.status_code)
    except Exception as e:
        logger.warning("notify(slack): failed: %s", e)

def _notify_email(message: str) -> None:
    host = os.environ.get("SMTP_HOST")
    to = os.environ.get("NOTIFY_EMAIL_TO")
    frm = os.environ.get("NOTIFY_EMAIL_FROM", to)
    if not host or not to:
        logger.warning("notify(email): SMTP_HOST or NOTIFY_EMAIL_TO not set; skipping")
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = "Review ready"
        msg["From"] = frm
        msg["To"] = to
        msg.set_content(message)
        port = int(os.environ.get("SMTP_PORT", "25"))
        with smtplib.SMTP(host, port, timeout=10) as s:
            if user := os.environ.get("SMTP_USER"):
                s.starttls()
                s.login(user, os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    except Exception as e:
        logger.warning("notify(email): failed: %s", e)
```

- [ ] **Step 4: Confirm PASS**
- [ ] **Step 5: Commit**

```bash
git add src/autobots_devtools_shared_lib/notify tests/unit/test_notify.py
git commit -m "feat(notify): add Slack/email notify helper"
```

---

## Task 3: Audit decorator (TDD)

**Depends on:** Task 0 findings, Task 1 payload.

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/review/audit.py`
- Create: `tests/unit/review/test_audit.py`

### 3a. Happy path: decorator records a new file write

- [ ] **Step 1: Failing test**

```python
# tests/unit/review/test_audit.py
from pathlib import Path
from unittest.mock import MagicMock
from autobots_devtools_shared_lib.dynagent.review.audit import audit_writes
from autobots_devtools_shared_lib.dynagent.review.payload import (
    ReviewPayload, load_payload, save_payload,
)

def _mk_payload(tmp_path: Path) -> Path:
    p = tmp_path / "payload.json"
    save_payload(p, ReviewPayload(pipeline_order=["writer-agent"]))
    return p

def test_audit_records_first_write(tmp_path):
    payload_path = _mk_payload(tmp_path)

    @audit_writes(payload_path_from=lambda rt: str(payload_path),
                  agent_name_from=lambda rt: rt.state["current_agent"])
    def fake_write(runtime, path: str, content: str) -> str:
        Path(tmp_path / path).write_text(content)
        return "ok"

    rt = MagicMock(state={"current_agent": "writer-agent"})
    fake_write(rt, "models/Order.java", "class Order {}")

    payload = load_payload(payload_path)
    assert len(payload.groups) == 1
    g = payload.groups[0]
    assert g.agent == "writer-agent"
    assert len(g.files) == 1
    assert g.files[0].path == "models/Order.java"
    assert g.files[0].status == "added"
```

- [ ] **Step 2: Confirm FAIL**
- [ ] **Step 3: Implement**

```python
# src/autobots_devtools_shared_lib/dynagent/review/audit.py
from __future__ import annotations
import logging
from functools import wraps
from typing import Any, Callable

from .payload import (
    FileChange, GroupReview, ReviewPayload, load_payload, save_payload,
    apply_suppression, compute_upstream_stale,
)

logger = logging.getLogger(__name__)

def audit_writes(
    *,
    payload_path_from: Callable[[Any], str],
    agent_name_from: Callable[[Any], str],
    path_arg: str = "path",
) -> Callable:
    """Wrap a write tool so each successful call records a FileChange in the payload."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(runtime, *args, **kwargs):
            result = fn(runtime, *args, **kwargs)
            try:
                payload_path = payload_path_from(runtime)
                agent = agent_name_from(runtime)
                file_path = kwargs.get(path_arg) or (args[0] if args else None)
                if not file_path:
                    return result
                _upsert(payload_path, agent, file_path)
            except Exception as e:  # audit must never break the underlying tool
                logger.warning("audit_writes: failed to record write: %s", e)
            return result
        return wrapper
    return decorator

def _upsert(payload_path: str, agent: str, file_path: str) -> None:
    payload = load_payload(payload_path)
    group = next((g for g in payload.groups if g.agent == agent), None)
    if group is None:
        group = GroupReview(agent=agent, agent_display=agent)
        payload.groups.append(group)
    existing = next((f for f in group.files if f.path == file_path), None)
    if existing is None:
        group.files.append(FileChange(path=file_path, status="added"))
    else:
        existing.status = "modified"
    apply_suppression(payload)
    compute_upstream_stale(payload)
    save_payload(payload_path, payload)
```

- [ ] **Step 4: Confirm PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat(review): audit_writes decorator — happy path"
```

### 3b. Last-writer-wins + failure safety

- [ ] **Step 1: Add tests**

```python
def test_audit_last_writer_wins_on_path(tmp_path):
    payload_path = _mk_payload(tmp_path)

    @audit_writes(payload_path_from=lambda rt: str(payload_path),
                  agent_name_from=lambda rt: rt.state["current_agent"])
    def fake_write(runtime, path: str, content: str) -> str: return "ok"

    fake_write(MagicMock(state={"current_agent": "agent-a"}), "shared.py", "x")
    fake_write(MagicMock(state={"current_agent": "agent-b"}), "shared.py", "y")

    payload = load_payload(payload_path)
    owning_agents = [g.agent for g in payload.groups if any(f.path == "shared.py" for f in g.files)]
    assert owning_agents == ["agent-a", "agent-b"]  # both groups record; in practice caller can dedupe

def test_audit_tool_still_returns_when_payload_missing(tmp_path, caplog):
    missing = tmp_path / "nope.json"
    @audit_writes(payload_path_from=lambda rt: str(missing),
                  agent_name_from=lambda rt: "a")
    def fake_write(runtime, path: str) -> str: return "ok"
    assert fake_write(MagicMock(state={}), "x.py") == "ok"
    assert "audit_writes" in caplog.text
```

- [ ] **Step 2: If first test surfaces a design question** (dedupe last-writer-wins across groups), discuss with human before implementing. Default: keep per-agent groups, do not move files between groups. MER will rarely hit cross-agent writes on the same path.

- [ ] **Step 3: Confirm PASS**
- [ ] **Step 4: Commit**

```bash
git commit -am "feat(review): audit_writes is failure-safe + records duplicate-path writes per agent"
```

---

## Task 4: Review orchestrator (TDD)

**Depends on:** Task 1.

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/review/orchestrator.py`
- Create: `tests/unit/review/test_orchestrator.py`

The orchestrator is the trickiest piece. Design as a pure state machine over payload diffs plus an IO layer that polls. Test the state machine directly; fake the polling.

### 4a. State transitions

- [ ] **Step 1: Failing tests** for a pure `step(payload) -> list[Action]` function.

```python
# tests/unit/review/test_orchestrator.py
from autobots_devtools_shared_lib.dynagent.review.orchestrator import (
    step, ActionReinvokeAgent, ActionApproveAll, ActionNotifyReady,
)
from autobots_devtools_shared_lib.dynagent.review.payload import (
    ReviewPayload, GroupReview, HistoryEntry,
)

def test_step_first_awaiting_review_emits_notify_ready_once():
    payload = ReviewPayload(status="awaiting_review", groups=[
        GroupReview(agent="a", agent_display="A", review_state="pending"),
    ])
    prev = None
    actions = step(prev, payload)
    assert any(isinstance(a, ActionNotifyReady) for a in actions)

    # Second call with no change → no notify
    actions2 = step(payload, payload)
    assert not any(isinstance(a, ActionNotifyReady) for a in actions2)

def test_step_group_changes_requested_triggers_reinvoke():
    prev = ReviewPayload(
        pipeline_order=["a", "b"],
        groups=[
            GroupReview(agent="a", agent_display="A", review_state="pending"),
            GroupReview(agent="b", agent_display="B", review_state="pending"),
        ],
    )
    cur = prev.model_copy(deep=True)
    cur.groups[0].review_state = "changes_requested"
    cur.history.append(HistoryEntry(ts="t", agent="a", action="changes_requested", feedback="use Long"))

    actions = step(prev, cur)
    reinvokes = [a for a in actions if isinstance(a, ActionReinvokeAgent)]
    assert len(reinvokes) == 1
    assert reinvokes[0].agent == "a"
    assert "use Long" in reinvokes[0].feedback_history[-1].feedback

def test_step_approved_triggers_approve_all():
    prev = ReviewPayload(status="awaiting_review")
    cur = prev.model_copy(deep=True)
    cur.status = "approved"
    actions = step(prev, cur)
    assert any(isinstance(a, ActionApproveAll) for a in actions)
```

- [ ] **Step 2: Confirm FAIL**
- [ ] **Step 3: Implement**

```python
# src/autobots_devtools_shared_lib/dynagent/review/orchestrator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from .payload import (
    ReviewPayload, HistoryEntry, load_payload, save_payload,
    compute_upstream_stale,
)

@dataclass
class ActionNotifyReady:
    pass

@dataclass
class ActionReinvokeAgent:
    agent: str
    feedback_history: list[HistoryEntry]

@dataclass
class ActionApproveAll:
    payload: ReviewPayload

Action = ActionNotifyReady | ActionReinvokeAgent | ActionApproveAll

def step(prev: Optional[ReviewPayload], cur: ReviewPayload) -> list[Action]:
    actions: list[Action] = []

    # First-arrival notify.
    if prev is None and cur.status == "awaiting_review":
        actions.append(ActionNotifyReady())

    # Per-group transitions to changes_requested.
    prev_states = {g.agent: g.review_state for g in (prev.groups if prev else [])}
    for g in cur.groups:
        if prev_states.get(g.agent) != "changes_requested" and g.review_state == "changes_requested":
            history_for_agent = [h for h in cur.history if h.agent == g.agent]
            actions.append(ActionReinvokeAgent(agent=g.agent, feedback_history=history_for_agent))

    # Top-level approve.
    if (prev is None or prev.status != "approved") and cur.status == "approved":
        actions.append(ActionApproveAll(payload=cur))

    return actions
```

- [ ] **Step 4: Confirm PASS**
- [ ] **Step 5: Commit**

### 4b. Orchestrator runtime (polling + dispatch)

- [ ] **Step 1: Failing async test** using `tmp_path` + manual payload edits.

```python
import asyncio
import pytest
from autobots_devtools_shared_lib.dynagent.review.orchestrator import ReviewOrchestrator
from autobots_devtools_shared_lib.dynagent.review.payload import save_payload, load_payload, ReviewPayload, GroupReview

async def test_orchestrator_dispatches_approve_all(tmp_path):
    p = tmp_path / "payload.json"
    save_payload(p, ReviewPayload(status="awaiting_review"))

    approved = asyncio.Event()
    async def on_approve_all(payload): approved.set()

    orch = ReviewOrchestrator(
        payload_path=str(p),
        agent_factory=lambda name: (_ for _ in ()).throw(AssertionError("no agent rerun expected")),
        on_approve_all=on_approve_all,
        on_notify_ready=None,
        poll_interval_s=0.05,
    )
    task = asyncio.create_task(orch.run())
    await asyncio.sleep(0.1)
    payload = load_payload(p); payload.status = "approved"; save_payload(p, payload)
    await asyncio.wait_for(approved.wait(), timeout=2.0)
    orch.stop(); await task
```

- [ ] **Step 2: Implement `ReviewOrchestrator`**

```python
class ReviewOrchestrator:
    def __init__(
        self,
        payload_path: str,
        agent_factory: Callable[[str], Any],
        on_approve_all: Callable[[ReviewPayload], Awaitable[None]],
        on_notify_ready: Optional[Callable[[], None]] = None,
        poll_interval_s: float = 2.0,
    ):
        self.payload_path = payload_path
        self.agent_factory = agent_factory
        self.on_approve_all = on_approve_all
        self.on_notify_ready = on_notify_ready
        self.poll_interval_s = poll_interval_s
        self._stop = False
        self._prev: Optional[ReviewPayload] = None

    def stop(self) -> None:
        self._stop = True

    async def run(self) -> None:
        import asyncio
        while not self._stop:
            try:
                cur = load_payload(self.payload_path)
                for action in step(self._prev, cur):
                    await self._dispatch(action, cur)
                self._prev = cur
            except FileNotFoundError:
                pass  # payload not yet created
            await asyncio.sleep(self.poll_interval_s)

    async def _dispatch(self, action: Action, cur: ReviewPayload) -> None:
        if isinstance(action, ActionNotifyReady):
            if self.on_notify_ready:
                self.on_notify_ready()
        elif isinstance(action, ActionReinvokeAgent):
            agent = self.agent_factory(action.agent)
            # Caller-defined agent must accept (feedback_history) kwarg; document this.
            await agent.ainvoke(feedback=action.feedback_history)
            # Flip group back to pending and mark downstream stale.
            cur = load_payload(self.payload_path)
            for g in cur.groups:
                if g.agent == action.agent:
                    g.review_state = "pending"
            compute_upstream_stale(cur)
            save_payload(self.payload_path, cur)
        elif isinstance(action, ActionApproveAll):
            await self.on_approve_all(action.payload)
```

- [ ] **Step 3: Confirm PASS**
- [ ] **Step 4: Commit**

```bash
git commit -am "feat(review): orchestrator polling + dispatch"
```

### 4c. Re-invoke flips state + marks downstream stale

- [ ] **Step 1: Test** covering the full request-changes loop end-to-end using a fake agent factory.
- [ ] **Step 2: Implement tweaks if needed** (already largely covered by 4b).
- [ ] **Step 3: Commit.**

---

## Task 5: Chainlit review element

**Depends on:** Task 1.

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/review_element/__init__.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/review_element/element.py`
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/review_element/src/ReviewElement.tsx`
- Create: `src/autobots_devtools_shared_lib/dynagent/ui/review_element/public/*` (build output)
- Create: `tests/integration/review/test_review_element.py`

**Heads-up:** React component has lower TDD density. Test the Python shim; smoke-test the bundle load; manual QA the UI once wired in MER.

### 5a. Python shim

- [ ] **Step 1: Failing test**

```python
# tests/integration/review/test_review_element.py
from autobots_devtools_shared_lib.dynagent.ui.review_element import build_review_element
from autobots_devtools_shared_lib.dynagent.review.payload import ReviewPayload

def test_build_review_element_returns_custom_element_with_payload_props():
    payload = ReviewPayload(status="awaiting_review")
    el = build_review_element(payload, on_mutation=lambda p: None)
    assert el.name == "review"
    assert el.props["payload"]["status"] == "awaiting_review"
```

- [ ] **Step 2: Implement**

```python
# element.py
from typing import Callable
import chainlit as cl
from ...review.payload import ReviewPayload

def build_review_element(
    payload: ReviewPayload,
    on_mutation: Callable[[ReviewPayload], None],
) -> cl.CustomElement:
    # on_mutation is invoked from Chainlit action handlers registered on the session.
    return cl.CustomElement(name="review", props={"payload": payload.model_dump()})
```

- [ ] **Step 3: Confirm PASS + commit**

### 5b. React component (no TDD; acceptance-by-render)

- [ ] **Step 1: Scaffold** a Chainlit custom element per Chainlit docs. The element reads `props.payload`, renders grouped cards with Approve / Request-changes / Expand-diff buttons, dispatches events to Chainlit actions.
- [ ] **Step 2: Register actions** on Python side (`@cl.action_callback("review:approve_group")`, `review:request_changes`, `review:approve_all`) that mutate payload via `on_mutation` callback plumbed through session storage.
- [ ] **Step 3: Bundle** (`pnpm build` or whatever the convention is) and check `public/` into git.
- [ ] **Step 4: Manual QA** against a fixture payload served from a throwaway Chainlit app.
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(review): Chainlit review element — React component + shim"
```

**Acceptance:** renders all three `review_state` badges, suppressed toggle hides/shows files, Approve-all is disabled when any group is non-approved or stale.

---

## Task 6: Public API surface + docs

**Files:**
- Modify: `src/autobots_devtools_shared_lib/__init__.py` (if it re-exports top-level)
- Modify: `src/autobots_devtools_shared_lib/dynagent/__init__.py`
- Modify: `src/autobots_devtools_shared_lib/dynagent/ui/__init__.py`
- Create: `docs/reference/review-framework.md`

- [ ] **Step 1: Re-export** `ReviewPayload`, `audit_writes`, `ReviewOrchestrator`, `review_element` (build helper), `notify`, `NotifyChannel` per the PRD's Public API block.
- [ ] **Step 2: Write `docs/reference/review-framework.md`** with: quickstart, full API, integration example.
- [ ] **Step 3: Confirm `import autobots_devtools_shared_lib; ... ` paths match PRD.**
- [ ] **Step 4: Commit.**

---

## Task 7: End-to-end smoke test

**Files:**
- Create: `tests/integration/review/test_end_to_end.py`

- [ ] **Step 1:** Fake agent factory + payload file + orchestrator. Simulate: create payload → orchestrator notifies → user request-changes on one group → agent factory receives feedback → pending flip → approve all → `on_approve_all` hook fires. No Chainlit.
- [ ] **Step 2:** Run under `pytest -m integration`.
- [ ] **Step 3:** Commit.

---

## Rollout

- [ ] **Step 1:** Bump version in `pyproject.toml` (0.6.0 → 0.7.0).
- [ ] **Step 2:** Update `CHANGELOG` / `docs/changes.md`.
- [ ] **Step 3:** Open PR, request review.
- [ ] **Step 4:** On merge, publish per `PUBLISHING.md`.
- [ ] **Step 5:** Start MER adoption plan (separate doc).

---

## Out of Scope (deferred)

- Line-level comments.
- Syntax-highlighted diffs.
- Per-agent commits.
- Auto-rerun of downstream agents on upstream changes.
- Redis pub/sub payload watch (polling only in v1).
- Concurrent-editor optimistic locking.
