import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.services.context.in_memory import InMemoryContextStore
from autobots_devtools_shared_lib.common.services.context.redis_store import (
    RedisContextStore,
    _RedisConfig,
)
from autobots_devtools_shared_lib.common.services.context.store import ContextStore

logger = get_logger(__name__)


@dataclass(slots=True)
class _ContextYamlConfig:
    backend: str = "memory"
    redis: _RedisConfig | None = None


class ContextConfigError(RuntimeError):
    """Raised when context configuration is invalid or unavailable."""


_CONTEXT_STORE_SINGLETON: ContextStore | None = None


def set_context_store(store: ContextStore) -> None:
    """Override the context store singleton programmatically.

    Call once at server startup (after settings are loaded) to inject a
    CacheBackedContextStore or any other ContextStore implementation.
    Bypasses YAML-based factory; get_context_store() short-circuits on non-None singleton.
    """
    global _CONTEXT_STORE_SINGLETON
    _CONTEXT_STORE_SINGLETON = store


def _load_yaml_config(config_path: Path) -> Mapping[str, Any]:
    if not config_path.exists():
        logger.info(
            "Context configuration file not found at %s; using in-memory store", config_path
        )
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover - defensive path
        msg = f"Failed to load context configuration from {config_path}: {exc!s}"
        logger.exception(msg)
        raise ContextConfigError(msg) from exc

    if not isinstance(raw, Mapping):
        msg = f"Context configuration at {config_path} must be a mapping."
        logger.exception(msg)
        raise ContextConfigError(msg)

    return raw


def _parse_yaml_config(raw: Mapping[str, Any]) -> _ContextYamlConfig:
    # No configuration present -> default to memory backend
    if not raw:
        return _ContextYamlConfig()

    context_section = raw.get("context") or {}
    if not isinstance(context_section, Mapping):
        msg = "The 'context' section in YAML configuration must be a mapping."
        logger.error(msg)
        raise ContextConfigError(msg)

    backend = str(context_section.get("backend", "memory")).lower()

    redis_cfg: _RedisConfig | None = None
    if backend == "redis":
        redis_section = context_section.get("redis") or {}
        if not isinstance(redis_section, Mapping):
            msg = "The 'context.redis' section in YAML configuration must be a mapping."
            logger.error(msg)
            raise ContextConfigError(msg)

        url = redis_section.get("url")
        if not isinstance(url, str) or not url:
            msg = "Redis backend requires a non-empty 'context.redis.url' value."
            logger.error(msg)
            raise ContextConfigError(msg)

        prefix = redis_section.get("prefix") or "dynagent_ctx"
        redis_cfg = _RedisConfig(url=url, prefix=str(prefix))

    return _ContextYamlConfig(backend=backend, redis=redis_cfg)


def get_context_store() -> ContextStore:
    """Return a ContextStore instance based on YAML configuration.

    Resolution rules:
    1. If DYNA_CONTEXT_CONFIG_PATH is not set, use InMemoryContextStore.
    2. If DYNA_CONTEXT_CONFIG_PATH is set, load YAML from that path.
    3. If no config file is found at that path, default to InMemoryContextStore.
    4. If a config file is found but is invalid or the backend cannot be constructed,
       raise ContextConfigError (fail fast).
    """
    global _CONTEXT_STORE_SINGLETON
    if _CONTEXT_STORE_SINGLETON is not None:
        return _CONTEXT_STORE_SINGLETON

    env_path = os.getenv("DYNA_CONTEXT_CONFIG_PATH")
    if not env_path:
        logger.info(
            "DYNA_CONTEXT_CONFIG_PATH not set; using InMemoryContextStore for dynagent context backend"
        )
        _CONTEXT_STORE_SINGLETON = InMemoryContextStore()
        return _CONTEXT_STORE_SINGLETON

    config_path = Path(env_path)
    raw = _load_yaml_config(config_path)
    parsed = _parse_yaml_config(raw)

    backend = parsed.backend
    if backend == "memory":
        logger.info("Using InMemoryContextStore for dynagent context backend")
        _CONTEXT_STORE_SINGLETON = InMemoryContextStore()
        return _CONTEXT_STORE_SINGLETON

    if backend == "redis":
        if parsed.redis is None:
            msg = "Redis backend selected but redis configuration is missing."
            logger.error(msg)
            raise ContextConfigError(msg)
        logger.info("Using RedisContextStore for dynagent context backend")
        _CONTEXT_STORE_SINGLETON = RedisContextStore(parsed.redis)
        return _CONTEXT_STORE_SINGLETON

    msg = f"Unsupported context backend '{backend}'. Supported backends are: 'memory', 'redis'."
    logger.error(msg)
    raise ContextConfigError(msg)
