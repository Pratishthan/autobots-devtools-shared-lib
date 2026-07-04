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


def lm(
    model: str | None = None,
    provider: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """Return an LLM instance; each argument defaults to the configured settings value."""
    settings = get_dynagent_settings()
    if provider is None:
        resolved_provider = settings.llm_provider
    else:
        try:
            resolved_provider = LLMProvider(provider)
        except ValueError:
            msg = f"Unsupported LLM provider: {provider}"
            raise ValueError(msg) from None
    resolved_model = model if model is not None else settings.llm_model
    resolved_temperature = temperature if temperature is not None else settings.llm_temperature

    if resolved_provider == LLMProvider.GEMINI:
        return _build_gemini(resolved_model, resolved_temperature, settings.google_api_key)
    if resolved_provider == LLMProvider.ANTHROPIC:
        return _build_anthropic(resolved_model, resolved_temperature, settings.anthropic_api_key)
    msg = f"Unsupported LLM provider: {resolved_provider}"
    raise ValueError(msg)
