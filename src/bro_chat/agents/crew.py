# ABOUTME: CrewAI crew definition for bro-chat.
# ABOUTME: Defines the agent team and their collaboration structure.

from typing import cast

from crewai import Agent, Crew, Process, Task

from bro_chat.agents.tools import get_default_tools
from bro_chat.config.settings import Settings, get_settings


def create_assistant_agent(settings: Settings) -> Agent:
    """
    Create the main assistant agent.

    Args:
        settings: Application settings.

    Returns:
        Configured Agent instance.
    """
    return Agent(
        role="Assistant",
        goal="Help users with their questions and tasks in a friendly, helpful manner",
        backstory=(
            "You are a knowledgeable and friendly assistant. You aim to provide "
            "clear, accurate, and helpful responses to any questions or tasks. "
            "You're patient and thorough in your explanations."
        ),
        tools=get_default_tools(),
        verbose=settings.debug,
        allow_delegation=False,
    )


def create_chat_task(agent: Agent, user_message: str) -> Task:
    """
    Create a task for responding to a user message.

    Args:
        agent: The agent to handle the task.
        user_message: The user's message to respond to.

    Returns:
        Configured Task instance.
    """
    return Task(
        description=f"Respond to the following user message: {user_message}",
        expected_output="A helpful, clear, and accurate response to the user.",
        agent=agent,
    )


def create_crew(settings: Settings | None = None) -> Crew:
    """
    Create the main crew for bro-chat.

    Args:
        settings: Optional settings instance. Uses get_settings() if not provided.

    Returns:
        Configured Crew instance.
    """
    if settings is None:
        settings = get_settings()

    assistant = create_assistant_agent(settings)

    return Crew(
        agents=[assistant],
        tasks=[],
        process=Process.sequential,
        verbose=settings.debug,
    )


async def run_chat(crew: Crew, user_message: str) -> str:
    """
    Run the crew to respond to a user message.

    Args:
        crew: The crew to run.
        user_message: The user's message.

    Returns:
        The crew's response.
    """
    assistant = cast(Agent, crew.agents[0])
    task = create_chat_task(assistant, user_message)

    crew.tasks = [task]
    result = crew.kickoff()

    return str(result)
