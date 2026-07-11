# ABOUTME: Generic stage-and-approve gate for supervised agentic apps.
# ABOUTME: Diff + Approve/Reject AskActionMessage + on_approve callback, returns ProposalOutcome.

from __future__ import annotations

import difflib
from enum import StrEnum
from typing import TYPE_CHECKING

import chainlit as cl

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)


class ProposalOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVAL_TIMEOUT = "approval_timeout"
    STORAGE_FAILED = "storage_failed"


def format_unified_diff(
    current: str,
    proposed: str,
    *,
    from_label: str = "current",
    to_label: str = "proposed",
) -> str:
    """Return a unified-diff string. Empty string when inputs are identical line-wise."""
    diff_lines = list(
        difflib.unified_diff(
            current.splitlines(),
            proposed.splitlines(),
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )
    )
    return "\n".join(diff_lines)


async def post_diff_message(
    target_name: str,
    diff_text: str,
    *,
    empty_message: str | None = None,
) -> None:
    if diff_text:
        body = f"Proposed update to **{target_name}**:\n\n```diff\n{diff_text}\n```"
    else:
        body = (
            empty_message
            or f"Proposed update to **{target_name}** (no textual changes after rendering)."
        )
    await cl.Message(content=body).send()


async def ask_approval(
    target_name: str,
    *,
    approve_label: str = "Approve",
    reject_label: str = "Reject",
    timeout: int | None = 90,
) -> str | None:
    """Render Approve/Reject buttons. Returns 'approve', 'reject', or None on timeout."""
    kwargs: dict = {
        "content": f"Apply this update to **{target_name}**?",
        "actions": [
            cl.Action(name="approve", payload={"value": "approve"}, label=approve_label),
            cl.Action(name="reject", payload={"value": "reject"}, label=reject_label),
        ],
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    res = await cl.AskActionMessage(**kwargs).send()
    if res is None:
        return None
    # cl.AskActionMessage returns AskActionResponse (TypedDict = plain dict at runtime).
    payload = res.get("payload") or {}
    return payload.get("value")


async def propose_change(
    *,
    target_name: str,
    current_text: str,
    proposed_text: str,
    on_approve: Callable[[], Awaitable[None]],
    on_approve_message: str | None = None,
    from_label: str = "current",
    to_label: str = "proposed",
    timeout: int | None = 90,
) -> ProposalOutcome:
    """Post a diff, ask Approve/Reject, run on_approve on approve.

    The caller is responsible for:
      * short-circuiting "no change" before calling (semantics are app-specific);
      * rendering current_text and proposed_text — failures here belong to the caller
        and should be surfaced via its own return values.

    Returns:
      APPROVED          — on_approve ran without raising.
      REJECTED          — user clicked Reject.
      APPROVAL_TIMEOUT  — AskActionMessage timed out with no choice.
      STORAGE_FAILED    — on_approve raised; a generic error message has been posted
                          to chat. The caller may surface a domain-specific code.
    """
    diff_text = format_unified_diff(
        current_text, proposed_text, from_label=from_label, to_label=to_label
    )
    await post_diff_message(target_name, diff_text)

    choice = await ask_approval(target_name, timeout=timeout)
    if choice is None:
        return ProposalOutcome.APPROVAL_TIMEOUT
    if choice != "approve":
        return ProposalOutcome.REJECTED

    try:
        await on_approve()
    except Exception:
        logger.exception("on_approve callback raised during propose_change")
        await cl.Message(content="Storage error — your update was not saved.").send()
        return ProposalOutcome.STORAGE_FAILED

    if on_approve_message:
        await cl.Message(content=on_approve_message).send()
    return ProposalOutcome.APPROVED
