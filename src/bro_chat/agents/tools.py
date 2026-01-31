# ABOUTME: Custom tools for CrewAI agents in bro-chat.
# ABOUTME: Placeholder tools that can be extended for specific agent capabilities.

from crewai.tools import BaseTool


class SearchTool(BaseTool):
    """A placeholder search tool for agents."""

    name: str = "search"
    description: str = "Search for information on a given topic."

    def _run(self, query: str) -> str:
        """
        Execute a search query.

        Args:
            query: The search query string.

        Returns:
            Search results as a string.
        """
        return f"Search results for: {query}\n\n[Placeholder - implement search]"


class CalculatorTool(BaseTool):
    """A simple calculator tool for agents."""

    name: str = "calculator"
    description: str = "Perform basic mathematical calculations."

    def _run(self, expression: str) -> str:
        """
        Evaluate a mathematical expression.

        Args:
            expression: The mathematical expression to evaluate.

        Returns:
            The result of the calculation.
        """
        try:
            result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
            return f"Result: {result}"
        except Exception as e:
            return f"Error evaluating expression: {e}"


def get_default_tools() -> list[BaseTool]:
    """
    Get the default set of tools for agents.

    Returns:
        List of default tools.
    """
    return [
        SearchTool(),
        CalculatorTool(),
    ]
