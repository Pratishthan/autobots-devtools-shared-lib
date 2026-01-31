# ABOUTME: Main package for bro-chat, a Chainlit chatbot with CrewAI agents.
# ABOUTME: Exports core components for chat UI, agents, and observability.

from bro_chat.config.settings import Settings

__version__ = "0.1.0"
__all__ = ["Settings", "__version__"]
