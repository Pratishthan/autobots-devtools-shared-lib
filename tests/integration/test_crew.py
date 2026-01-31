# ABOUTME: Integration tests for CrewAI crew functionality.
# ABOUTME: Tests agent creation and crew orchestration.

from bro_chat.agents.crew import (
    create_assistant_agent,
    create_chat_task,
    create_crew,
)
from bro_chat.agents.tools import CalculatorTool, SearchTool, get_default_tools
from bro_chat.config.settings import Settings
from tests.conftest import requires_openai


class TestTools:
    """Tests for agent tools."""

    def test_search_tool_has_correct_name(self) -> None:
        """SearchTool should have the correct name."""
        tool = SearchTool()
        assert tool.name == "search"

    def test_search_tool_returns_placeholder(self) -> None:
        """SearchTool should return placeholder results."""
        tool = SearchTool()
        result = tool._run("test query")
        assert "test query" in result
        assert "Placeholder" in result

    def test_calculator_tool_evaluates_expression(self) -> None:
        """CalculatorTool should evaluate mathematical expressions."""
        tool = CalculatorTool()
        result = tool._run("2 + 2")
        assert "4" in result

    def test_calculator_tool_handles_errors(self) -> None:
        """CalculatorTool should handle invalid expressions."""
        tool = CalculatorTool()
        result = tool._run("invalid")
        assert "Error" in result

    def test_get_default_tools_returns_list(self) -> None:
        """get_default_tools should return a list of tools."""
        tools = get_default_tools()
        assert isinstance(tools, list)
        assert len(tools) == 2


class TestAgentCreation:
    """Tests for agent creation (requires OpenAI API key)."""

    @requires_openai
    def test_create_assistant_agent(self, test_settings: Settings) -> None:
        """create_assistant_agent should create a properly configured agent."""
        agent = create_assistant_agent(test_settings)

        assert agent.role == "Assistant"
        assert "help" in agent.goal.lower()
        assert agent.verbose is True  # debug=True in test_settings

    @requires_openai
    def test_agent_has_tools(self, test_settings: Settings) -> None:
        """Assistant agent should have default tools."""
        agent = create_assistant_agent(test_settings)

        assert agent.tools is not None
        assert len(agent.tools) > 0


class TestCrewCreation:
    """Tests for crew creation (requires OpenAI API key)."""

    @requires_openai
    def test_create_crew_returns_crew(self, test_settings: Settings) -> None:
        """create_crew should return a Crew instance."""
        crew = create_crew(test_settings)

        assert crew is not None
        assert len(crew.agents) == 1

    @requires_openai
    def test_crew_uses_settings(self, test_settings: Settings) -> None:
        """create_crew should use provided settings."""
        crew = create_crew(test_settings)

        assert crew.verbose is True


class TestTaskCreation:
    """Tests for task creation (requires OpenAI API key)."""

    @requires_openai
    def test_create_chat_task(self, test_settings: Settings) -> None:
        """create_chat_task should create a task for the message."""
        agent = create_assistant_agent(test_settings)
        task = create_chat_task(agent, "Hello, world!")

        assert "Hello, world!" in task.description
        assert task.agent == agent
