# ABOUTME: Unit tests for BRO usecase_ui helper functions.
# ABOUTME: Validates get_preloaded_prompts without requiring a Chainlit runtime.

from types import SimpleNamespace

from bro_chat.usecase_ui import get_preloaded_prompts


def _msg(content: str, command: str | None = None) -> SimpleNamespace:
    """Minimal stand-in for cl.Message with just the fields we need."""
    return SimpleNamespace(content=content, command=command)


def test_get_preloaded_prompts_view_context():
    """View-Context command returns the fixed get_context prompt."""
    msg = _msg("ignored", command="View-Context")
    assert get_preloaded_prompts(msg) == (
        "Get and display the current SDLC context using get_context tool"
    )


def test_get_preloaded_prompts_edit_context():
    """Edit-Context command returns the LLD Consolidator prompt."""
    msg = _msg("ignored", command="Edit-Context")
    assert get_preloaded_prompts(msg) == "Start LLD Consolidator Assistant"


def test_get_preloaded_prompts_plain_message():
    """No command → raw message content is returned as the prompt."""
    msg = _msg("hello world", command=None)
    assert get_preloaded_prompts(msg) == "hello world"
