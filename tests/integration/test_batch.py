# ABOUTME: Integration tests for batch_invoker against a live Gemini backend.
# ABOUTME: bro_registered_integration (autouse) in conftest handles tool registration.

from autobots_devtools_shared_lib.dynagent.agents.batch import batch_invoker
from tests.conftest import requires_google_api


@requires_google_api
def test_batch_invoker_single_record():
    """One record completes with non-empty output."""
    result = batch_invoker("coordinator", ["Hello, what can you help with?"])
    assert result.total == 1
    assert len(result.successes) == 1
    assert result.successes[0].output is not None
    assert len(result.successes[0].output) > 0


@requires_google_api
def test_batch_invoker_multiple_records():
    """Three records all succeed independently."""
    prompts = [
        "What is this system for?",
        "Can you list the agents?",
        "Tell me about vision documents.",
    ]
    result = batch_invoker("coordinator", prompts)
    assert result.total == 3
    assert len(result.successes) == 3
    assert len(result.failures) == 0


@requires_google_api
def test_batch_invoker_results_are_independent():
    """Different prompts produce different outputs (thread isolation proof)."""
    prompts = [
        "Say the word ALPHA and nothing else.",
        "Say the word BETA and nothing else.",
    ]
    result = batch_invoker("coordinator", prompts)
    assert len(result.successes) == 2
    outputs = [r.output or "" for r in result.successes]
    # Outputs must differ — proves threads didn't share state
    assert outputs[0] != outputs[1]


@requires_google_api
def test_batch_invoker_result_indices_are_sequential():
    """Indices are 0, 1, 2 matching input order."""
    prompts = ["first", "second", "third"]
    result = batch_invoker("coordinator", prompts)
    indices = [r.index for r in result.results]
    assert indices == [0, 1, 2]


@requires_google_api
def test_batch_invoker_section_agent():
    """Works with preface_agent, not just coordinator."""
    result = batch_invoker("preface_agent", ["What is the preface section about?"])
    assert result.total == 1
    assert len(result.successes) == 1
    assert result.successes[0].output is not None


@requires_google_api
def test_batch_invoker_agent_name_preserved():
    """BatchResult.agent_name reflects the input agent name."""
    result = batch_invoker("coordinator", ["Hi"])
    assert result.agent_name == "coordinator"
