# ABOUTME: Smoke test that the deepagents dependency is installed and importable.
# ABOUTME: Guards the Phase 0 langchain-stack upgrade that unblocks the deep engine.


def test_deepagents_imports():
    from deepagents import DeepAgentState, SubAgent, create_deep_agent

    assert create_deep_agent is not None
    assert DeepAgentState is not None
    assert SubAgent is not None


def test_langgraph_stream_module_present():
    import importlib

    # deepagents imports langgraph.stream.run_stream; this is the module that
    # is absent when the langchain stack is too old.
    assert importlib.import_module("langgraph.stream") is not None
