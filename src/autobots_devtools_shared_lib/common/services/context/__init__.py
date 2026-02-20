"""Context storage: protocols, implementations, and YAML-based factory.

Re-exports all public types and the factory so that:
  from autobots_devtools_shared_lib.common.services.context import ...
continues to work. Tests may also use this module for monkeypatching
(_CONTEXT_STORE_SINGLETON, _load_yaml_config).
"""

from autobots_devtools_shared_lib.common.services.context.cache_backed import (
    CacheBackedContextStore,
)
from autobots_devtools_shared_lib.common.services.context.db_repository import DbRepository
from autobots_devtools_shared_lib.common.services.context.factory import (
    _CONTEXT_STORE_SINGLETON,
    ContextConfigError,
    _load_yaml_config,
    get_context_store,
    set_context_store,
)
from autobots_devtools_shared_lib.common.services.context.in_memory import InMemoryContextStore
from autobots_devtools_shared_lib.common.services.context.redis_store import (
    RedisContextStore,
    _RedisConfig,
)
from autobots_devtools_shared_lib.common.services.context.store import ContextStore

__all__ = [
    "_CONTEXT_STORE_SINGLETON",
    "CacheBackedContextStore",
    "ContextConfigError",
    "ContextStore",
    "DbRepository",
    "InMemoryContextStore",
    "RedisContextStore",
    "_RedisConfig",
    "_load_yaml_config",
    "get_context_store",
    "set_context_store",
]
