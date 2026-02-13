# ABOUTME: LLM factory for the dynagent reference architecture.
# ABOUTME: Returns a configured LLM instance based on the selected provider.

from langchain.chat_models import BaseChatModel

from autobots_devtools_shared_lib.dynagent.config.settings import LLMProvider, get_settings


def _build_gemini(model: str, temperature: float) -> BaseChatModel:
    """Build a Google Gemini chat model."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model, temperature=temperature)


def _build_anthropic(model: str, temperature: float) -> BaseChatModel:
    """Build an Anthropic chat model."""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model_name=model, temperature=temperature)  # type: ignore[call-arg]


_BUILDER = {
    LLMProvider.GEMINI: _build_gemini,
    LLMProvider.ANTHROPIC: _build_anthropic,
}


def lm() -> BaseChatModel:
    """Return the default LLM instance based on the configured provider."""
    settings = get_settings()
    builder = _BUILDER.get(settings.llm_provider)
    if builder is None:
        msg = f"Unsupported LLM provider: {settings.llm_provider}"
        raise ValueError(msg)
    return builder(settings.llm_model, settings.llm_temperature)
