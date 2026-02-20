from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


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

    def _key(self, context_key: str) -> str:
        return f"{self._prefix}_{context_key}"

    def get(self, context_key: str) -> dict[str, Any] | None:
        import json

        value = self._redis.get(self._key(context_key))
        if value is None:
            return None
        try:
            # Sync redis.Redis.get returns bytes | None; stubs use generic ResponseT
            return json.loads(cast("str | bytes | bytearray", value))
        except Exception:  # pragma: no cover - defensive path
            logger.exception("Failed to decode context for context_key %s", context_key)
            raise

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:
        import json

        payload = json.dumps(dict(data))
        self._redis.set(self._key(context_key), payload)

    def update(self, context_key: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self.get(context_key) or {}
        updated = {**current, **dict(patch)}
        self.set(context_key, updated)
        return updated

    def delete(self, context_key: str) -> None:
        self._redis.delete(self._key(context_key))
