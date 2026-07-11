# ABOUTME: Unit tests for the generic approval gate utility.
# ABOUTME: Covers diff formatting, AskActionResponse TypedDict access, and propose_change flow.

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autobots_devtools_shared_lib.dynagent.ui.approval_gate import (
    ProposalOutcome,
    ask_approval,
    format_unified_diff,
    post_diff_message,
    propose_change,
)

# ---------------------------------------------------------------------------
# format_unified_diff — pure
# ---------------------------------------------------------------------------


def test_format_unified_diff_marks_changes():
    out = format_unified_diff("a\nb\nc\n", "a\nB\nc\n", from_label="cur", to_label="new")
    assert "--- cur" in out
    assert "+++ new" in out
    assert "-b" in out
    assert "+B" in out


def test_format_unified_diff_identical_inputs_returns_empty():
    assert format_unified_diff("x\ny\n", "x\ny\n") == ""


def test_format_unified_diff_default_labels():
    out = format_unified_diff("a\n", "b\n")
    assert "--- current" in out
    assert "+++ proposed" in out


# ---------------------------------------------------------------------------
# Test scaffolding for chainlit-coupled code paths
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_cl():
    """Patch every chainlit symbol the module touches; return the mocks."""
    msg_send = AsyncMock(return_value=None)
    ask_send = AsyncMock()

    msg_instance = MagicMock()
    msg_instance.send = msg_send
    ask_instance = MagicMock()
    ask_instance.send = ask_send

    with (
        patch(
            "autobots_devtools_shared_lib.dynagent.ui.approval_gate.cl.Message",
            return_value=msg_instance,
        ) as msg_cls,
        patch(
            "autobots_devtools_shared_lib.dynagent.ui.approval_gate.cl.AskActionMessage",
            return_value=ask_instance,
        ) as ask_cls,
        patch(
            "autobots_devtools_shared_lib.dynagent.ui.approval_gate.cl.Action",
            return_value=MagicMock(),
        ) as action_cls,
    ):
        yield {
            "Message": msg_cls,
            "AskActionMessage": ask_cls,
            "Action": action_cls,
            "msg_send": msg_send,
            "ask_send": ask_send,
        }


# ---------------------------------------------------------------------------
# ask_approval — regression guard for the AskActionResponse TypedDict access
# ---------------------------------------------------------------------------


async def test_ask_approval_returns_approve(patched_cl):
    patched_cl["ask_send"].return_value = {
        "payload": {"value": "approve"},
        "name": "approve",
        "label": "Approve",
    }
    assert await ask_approval("Section X") == "approve"


async def test_ask_approval_returns_reject(patched_cl):
    patched_cl["ask_send"].return_value = {
        "payload": {"value": "reject"},
        "name": "reject",
        "label": "Reject",
    }
    assert await ask_approval("Section X") == "reject"


async def test_ask_approval_returns_none_on_timeout(patched_cl):
    patched_cl["ask_send"].return_value = None
    assert await ask_approval("Section X") is None


async def test_ask_approval_handles_missing_payload(patched_cl):
    """Defensive: if a future chainlit version omits 'payload', return None instead of crashing."""
    patched_cl["ask_send"].return_value = {"name": "approve", "label": "Approve"}
    assert await ask_approval("Section X") is None


async def test_ask_approval_passes_timeout_when_provided(patched_cl):
    patched_cl["ask_send"].return_value = None
    await ask_approval("Section X", timeout=10)
    kwargs = patched_cl["AskActionMessage"].call_args.kwargs
    assert kwargs["timeout"] == 10


async def test_ask_approval_omits_timeout_when_none(patched_cl):
    patched_cl["ask_send"].return_value = None
    await ask_approval("Section X", timeout=None)
    kwargs = patched_cl["AskActionMessage"].call_args.kwargs
    assert "timeout" not in kwargs


# ---------------------------------------------------------------------------
# post_diff_message — body construction
# ---------------------------------------------------------------------------


async def test_post_diff_message_with_diff(patched_cl):
    await post_diff_message("Preface", "--- a\n+++ b\n-x\n+y")
    body = patched_cl["Message"].call_args.kwargs["content"]
    assert "Proposed update to **Preface**" in body
    assert "```diff" in body
    assert "-x" in body


async def test_post_diff_message_empty_diff_default_message(patched_cl):
    await post_diff_message("Preface", "")
    body = patched_cl["Message"].call_args.kwargs["content"]
    assert "no textual changes" in body


async def test_post_diff_message_empty_diff_custom_message(patched_cl):
    await post_diff_message("Preface", "", empty_message="Nothing changed.")
    body = patched_cl["Message"].call_args.kwargs["content"]
    assert body == "Nothing changed."


# ---------------------------------------------------------------------------
# propose_change — orchestration
# ---------------------------------------------------------------------------


async def test_propose_change_approved_runs_callback(patched_cl):
    patched_cl["ask_send"].return_value = {"payload": {"value": "approve"}}
    on_approve = AsyncMock()
    outcome = await propose_change(
        target_name="X",
        current_text="a\n",
        proposed_text="b\n",
        on_approve=on_approve,
    )
    assert outcome == ProposalOutcome.APPROVED
    on_approve.assert_awaited_once()


async def test_propose_change_rejected_skips_callback(patched_cl):
    patched_cl["ask_send"].return_value = {"payload": {"value": "reject"}}
    on_approve = AsyncMock()
    outcome = await propose_change(
        target_name="X",
        current_text="a\n",
        proposed_text="b\n",
        on_approve=on_approve,
    )
    assert outcome == ProposalOutcome.REJECTED
    on_approve.assert_not_awaited()


async def test_propose_change_timeout(patched_cl):
    patched_cl["ask_send"].return_value = None
    on_approve = AsyncMock()
    outcome = await propose_change(
        target_name="X",
        current_text="a\n",
        proposed_text="b\n",
        on_approve=on_approve,
    )
    assert outcome == ProposalOutcome.APPROVAL_TIMEOUT
    on_approve.assert_not_awaited()


async def test_propose_change_storage_failure(patched_cl):
    patched_cl["ask_send"].return_value = {"payload": {"value": "approve"}}
    on_approve = AsyncMock(side_effect=RuntimeError("disk full"))
    outcome = await propose_change(
        target_name="X",
        current_text="a\n",
        proposed_text="b\n",
        on_approve=on_approve,
    )
    assert outcome == ProposalOutcome.STORAGE_FAILED
    on_approve.assert_awaited_once()
    # The user-facing storage-error message must have been posted.
    posted_bodies = [c.kwargs["content"] for c in patched_cl["Message"].call_args_list]
    assert any("Storage error" in b for b in posted_bodies)


async def test_propose_change_approved_posts_success_message_when_provided(patched_cl):
    patched_cl["ask_send"].return_value = {"payload": {"value": "approve"}}
    await propose_change(
        target_name="X",
        current_text="a\n",
        proposed_text="b\n",
        on_approve=AsyncMock(),
        on_approve_message="**X** updated.",
    )
    posted_bodies = [c.kwargs["content"] for c in patched_cl["Message"].call_args_list]
    assert "**X** updated." in posted_bodies


async def test_propose_change_approved_no_success_message_when_omitted(patched_cl):
    patched_cl["ask_send"].return_value = {"payload": {"value": "approve"}}
    await propose_change(
        target_name="X",
        current_text="a\n",
        proposed_text="b\n",
        on_approve=AsyncMock(),
    )
    posted_bodies = [c.kwargs["content"] for c in patched_cl["Message"].call_args_list]
    # Only the diff message; no extra success post.
    assert len(posted_bodies) == 1


# ---------------------------------------------------------------------------
# ProposalOutcome — StrEnum identity
# ---------------------------------------------------------------------------


def test_proposal_outcome_compares_as_string():
    assert ProposalOutcome.APPROVED == "approved"
    assert ProposalOutcome.REJECTED == "rejected"
    assert ProposalOutcome.APPROVAL_TIMEOUT == "approval_timeout"
    assert ProposalOutcome.STORAGE_FAILED == "storage_failed"


def test_proposal_outcome_serialises_as_string():
    assert json.dumps({"x": ProposalOutcome.APPROVED}) == '{"x": "approved"}'
