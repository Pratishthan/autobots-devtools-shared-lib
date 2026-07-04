# ABOUTME: Deep-engine middleware that merges all SystemMessages into one leading block.
# ABOUTME: Lets CopilotKitMiddleware run under Anthropic (no "multiple non-consecutive system messages").

from langchain.agents.middleware import wrap_model_call
from langchain.messages import SystemMessage


def _text(content) -> str:
    return content if isinstance(content, str) else str(content)


@wrap_model_call  # type: ignore[arg-type]
async def collapse_system_messages(request, handler):
    """Merge the dedicated system message + every inline SystemMessage into one leading block.

    Preserves all system content (unlike the classic inject_agent, which discards inline
    system messages) while satisfying Anthropic's 'system must be single/leading' rule.
    A no-op when there is at most one system message overall.
    """
    inline = [m for m in request.messages if isinstance(m, SystemMessage)]
    rest = [m for m in request.messages if not isinstance(m, SystemMessage)]

    base = request.system_message
    if len(inline) == 0:
        # No-op: no inline system messages to merge
        merged_system = base
    else:
        # Merge base and inline system messages
        parts = []
        if base is not None:
            parts.append(_text(base.content))
        parts.extend(_text(m.content) for m in inline)
        merged = "\n\n".join(p for p in parts if p)
        merged_system = SystemMessage(content=merged) if merged else base

    new_request = request.override(
        messages=rest,
        system_message=merged_system,
    )
    return await handler(new_request)
