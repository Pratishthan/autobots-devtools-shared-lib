# ABOUTME: Integration tests for bro_batch against a live Gemini backend.
# ABOUTME: bro_registered_integration (autouse) in conftest handles tool registration.

import pytest

from bro_chat.services.bro_batch import bro_batch
from tests.conftest import requires_google_api


@requires_google_api
def test_bro_batch_single_record_coordinator():
    """One record through coordinator completes with non-empty output."""
    result = bro_batch("coordinator", ["Hello, what can you help with?"])
    assert result.total == 1
    assert len(result.successes) == 1
    assert result.successes[0].output is not None
    assert len(result.successes[0].output) > 0


@requires_google_api
def test_bro_batch_multiple_records():
    """Three records all succeed independently."""
    prompts = [
        "What is this system for?",
        "Can you list the agents?",
        "Tell me about vision documents.",
    ]
    result = bro_batch("coordinator", prompts)
    assert result.total == 3
    assert len(result.successes) == 3
    assert len(result.failures) == 0


@requires_google_api
def test_bro_batch_results_are_independent():
    """Different prompts produce different outputs (session isolation proof)."""
    prompts = [
        "Say the word ALPHA and nothing else.",
        "Say the word BETA and nothing else.",
    ]
    result = bro_batch("coordinator", prompts)
    assert len(result.successes) == 2
    outputs = [r.output or "" for r in result.successes]
    # Outputs must differ — proves sessions didn't share state
    assert outputs[0] != outputs[1]


@requires_google_api
def test_bro_batch_result_indices_are_sequential():
    """Indices are 0, 1, 2 matching input order."""
    prompts = ["first", "second", "third"]
    result = bro_batch("coordinator", prompts)
    indices = [r.index for r in result.results]
    assert indices == [0, 1, 2]


@requires_google_api
def test_bro_batch_section_agent():
    """Works with preface_agent, not just coordinator."""
    result = bro_batch("preface_agent", ["What is the preface section about?"])
    assert result.total == 1
    assert len(result.successes) == 1
    assert result.successes[0].output is not None


@requires_google_api
def test_bro_batch_agent_name_preserved():
    """BatchResult.agent_name reflects the input agent name."""
    result = bro_batch("coordinator", ["Hi"])
    assert result.agent_name == "coordinator"


def test_bro_batch_rejects_non_bro_agent():
    """BRO gate fires before any LLM call — no API key needed."""
    with pytest.raises(ValueError, match="Unknown BRO agent"):
        bro_batch("not_a_bro_agent", ["hello"])
