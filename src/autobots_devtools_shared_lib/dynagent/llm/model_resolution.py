# ABOUTME: Resolves per-agent model config (profile name / inline provider:name / bare name).
# ABOUTME: Validation runs at config load; resolution builds BaseChatModel instances via lm().

from typing import Any

from langchain.chat_models import BaseChatModel

from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import LLMProvider
from autobots_devtools_shared_lib.dynagent.llm.llm import lm

_KNOWN_PROVIDERS = {provider.value for provider in LLMProvider}


def validate_model_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    """Fail fast on a models: profile naming an unsupported provider."""
    for profile_name, profile in profiles.items():
        provider = profile.get("provider")
        if provider is not None and provider not in _KNOWN_PROVIDERS:
            msg = (
                f"Model profile '{profile_name}' has unsupported provider '{provider}'. "
                f"Supported providers: {sorted(_KNOWN_PROVIDERS)}"
            )
            raise ValueError(msg)


def validate_model_ref(ref: str, profiles: dict[str, dict[str, Any]]) -> None:
    """Fail fast on a model: value that is neither a known profile nor parseable inline.

    Lookup order matches resolution: profile name first, then inline
    "provider:name" (provider must be supported), then bare model name
    (always valid — resolved against the settings provider).
    """
    if ref in profiles:
        return
    provider, _, model = ref.partition(":")
    if model and provider not in _KNOWN_PROVIDERS:
        msg = (
            f"model: '{ref}' is neither a known profile ({sorted(profiles)}) nor an inline "
            f"ref with a supported provider ({sorted(_KNOWN_PROVIDERS)})"
        )
        raise ValueError(msg)


def resolve_model_ref(ref: str | None, profiles: dict[str, dict[str, Any]]) -> BaseChatModel:
    """Resolve a model ref through lm(); None means the settings-configured default."""
    if ref is None:
        return lm()
    if ref in profiles:
        profile = profiles[ref]
        return lm(
            model=profile.get("name"),
            provider=profile.get("provider"),
            temperature=profile.get("temperature"),
        )
    provider, _, model = ref.partition(":")
    if model:
        return lm(model=model, provider=provider, temperature=None)
    return lm(model=ref, provider=None, temperature=None)


def resolve_agent_model(meta: Any, agent_name: str) -> BaseChatModel:
    """Resolve an agent's configured model, falling back to the settings default."""
    return resolve_model_ref(meta.model_map.get(agent_name), meta.model_profiles)
