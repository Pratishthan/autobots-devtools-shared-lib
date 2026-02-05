# ABOUTME: Import smoke tests for the refactored UI layer.
# ABOUTME: Verifies modules load without error and the re-export chain holds.


def test_dynagent_ui_utils_importable():
    """dynagent.ui.ui_utils loads cleanly and exposes expected symbols."""
    import autobots_devtools_shared_lib.dynagent.ui.ui_utils as mod

    assert callable(mod.structured_to_markdown)
    assert callable(mod.format_dict_item)
    assert callable(mod._extract_output_type)
    assert callable(mod.stream_agent_events)


def test_dynagent_default_ui_importable():
    """dynagent.ui.default_ui loads cleanly (Chainlit decorators register)."""
    import autobots_devtools_shared_lib.dynagent.ui.default_ui as mod  # noqa: F401


def test_bro_usecase_ui_importable():
    """bro_chat.usecase_ui loads cleanly; registration side-effects run."""
    import bro_chat.usecase_ui as mod  # noqa: F401


def test_formatting_re_export_works():
    """The re-export in bro_chat.utils.formatting resolves to the dynagent origin."""
    from bro_chat.utils.formatting import structured_to_markdown
    from autobots_devtools_shared_lib.dynagent.ui.ui_utils import (
        structured_to_markdown as canonical,
    )

    # Should be the exact same function object
    assert structured_to_markdown is canonical
