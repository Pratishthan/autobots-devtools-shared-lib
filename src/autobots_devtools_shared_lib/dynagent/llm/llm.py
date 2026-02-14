# ABOUTME: LLM factory for the dynagent reference architecture.
# ABOUTME: Returns a configured LLM instance based on the selected provider.

from langchain.chat_models import BaseChatModel

from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    LLMProvider,
    get_dynagent_settings,
)


def _build_gemini(model: str, temperature: float, api_key: str) -> BaseChatModel:
    """Build a Google Gemini chat model."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model, temperature=temperature, api_key=api_key or None)


def _build_anthropic(model: str, temperature: float, api_key: str) -> BaseChatModel:
    """Build an Anthropic chat model."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model_name=model, temperature=temperature, api_key=api_key or None)  # type: ignore[call-arg]


def lm() -> BaseChatModel:
    """Return the default LLM instance based on the configured provider."""
    settings = get_dynagent_settings()
    if settings.llm_provider == LLMProvider.GEMINI:
        return _build_gemini(settings.llm_model, settings.llm_temperature, settings.google_api_key)
    if settings.llm_provider == LLMProvider.ANTHROPIC:
        return _build_anthropic(
            settings.llm_model, settings.llm_temperature, settings.anthropic_api_key
        )
    msg = f"Unsupported LLM provider: {settings.llm_provider}"
    raise ValueError(msg)
