"""Unit tests for create_base_agent opt-in parameters."""

import inspect

from autobots_devtools_shared_lib.dynagent.agents.base_agent import create_base_agent


class TestCreateBaseAgentSignature:
    def test_accepts_enable_todos(self):
        sig = inspect.signature(create_base_agent)
        assert "enable_todos" in sig.parameters
        assert sig.parameters["enable_todos"].default is False

    def test_accepts_progress_domain(self):
        sig = inspect.signature(create_base_agent)
        assert "progress_domain" in sig.parameters
        assert sig.parameters["progress_domain"].default is None
