# ABOUTME: LLM factory for the dynagent reference architecture.
# ABOUTME: Returns a configured ChatGoogleGenerativeAI instance.

from langchain_google_genai import ChatGoogleGenerativeAI

from autobots_devtools_shared_lib.dynagent.config.settings import get_settings


def lm() -> ChatGoogleGenerativeAI:
    """Return the default LLM instance."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.llm_model, temperature=settings.llm_temperature
    )
