import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

import yaml

logger = logging.getLogger(__name__)


@runtime_checkable
class ContextStore(Protocol):
    """Protocol for session-level context storage.

    Context is modeled as a JSON-serializable mapping of string keys to arbitrary values.
    Implementations are responsible for persistence and retrieval semantics.
    """

    def get(self, session_id: str) -> dict[str, Any] | None:  # pragma: no cover - Protocol
        """Return the context for the given session_id, or None if not found."""

    def set(self, session_id: str, data: Mapping[str, Any]) -> None:  # pragma: no cover - Protocol
        """Replace the context for the given session_id with the provided data."""

    def update(
        self, session_id: str, patch: Mapping[str, Any]
    ) -> dict[str, Any]:  # pragma: no cover - Protocol
        """Apply a partial update to the context and return the new value."""
        ...

    def delete(self, session_id: str) -> None:  # pragma: no cover - Protocol
        """Remove any stored context for the given session_id."""


class InMemoryContextStore:
    """In-memory implementation of ContextStore.

    Suitable for development, testing, and ephemeral single-process runs.
    Not safe for multi-process deployments.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, session_id: str) -> dict[str, Any] | None:
        return self._store.get(session_id)

    def set(self, session_id: str, data: Mapping[str, Any]) -> None:
        self._store[session_id] = dict(data)

    def update(self, session_id: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self._store.get(session_id, {})
        # Create a shallow copy to avoid mutating the original dict outside this store
        updated = {**current, **dict(patch)}
        self._store[session_id] = updated
        return updated

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)


@dataclass(slots=True)
class _RedisConfig:
    url: str
    prefix: str = "dynagent_ctx"


class RedisContextStore:
    """Redis-backed ContextStore.

    Stores each session's context as a JSON-encoded string under a namespaced key.
    """

    def __init__(self, config: _RedisConfig) -> None:
        try:
            import redis  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - import failure path
            msg = "Redis client library is required for RedisContextStore but is not installed."
            logger.exception(msg)
            raise RuntimeError(msg) from exc

        self._redis = redis.Redis.from_url(config.url)
        self._prefix = config.prefix

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}:{session_id}"

    def get(self, session_id: str) -> dict[str, Any] | None:
        import json

        value = self._redis.get(self._key(session_id))
        if value is None:
            return None
        try:
            # Sync redis.Redis.get returns bytes | None; stubs use generic ResponseT
            return json.loads(cast("str | bytes | bytearray", value))
        except Exception:  # pragma: no cover - defensive path
            logger.exception("Failed to decode context for session_id %s", session_id)
            raise

    def set(self, session_id: str, data: Mapping[str, Any]) -> None:
        import json

        payload = json.dumps(dict(data))
        self._redis.set(self._key(session_id), payload)

    def update(self, session_id: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self.get(session_id) or {}
        updated = {**current, **dict(patch)}
        self.set(session_id, updated)
        return updated

    def delete(self, session_id: str) -> None:
        self._redis.delete(self._key(session_id))


@dataclass(slots=True)
class _ContextYamlConfig:
    backend: str = "memory"
    redis: _RedisConfig | None = None


class ContextConfigError(RuntimeError):
    """Raised when context configuration is invalid or unavailable."""


_CONTEXT_STORE_SINGLETON: ContextStore | None = None


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
    1. If DYNA_CONTEXT_CONFIG_PATH is set, load YAML from that path.
    2. Otherwise, attempt to load from the default path: configs/dynagent/context.yaml.
    3. If no config file is found, default to InMemoryContextStore.
    4. If a config file is found but is invalid or the backend cannot be constructed,
       raise ContextConfigError (fail fast).
    """
    import os

    global _CONTEXT_STORE_SINGLETON
    if _CONTEXT_STORE_SINGLETON is not None:
        return _CONTEXT_STORE_SINGLETON

    env_path = os.getenv("DYNA_CONTEXT_CONFIG_PATH")
    config_path = Path(env_path) if env_path else Path("configs") / "dynagent" / "context.yaml"

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
