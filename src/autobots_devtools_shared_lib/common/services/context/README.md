# Context store: DbRepository and CacheBackedContextStore

This package provides a **DbRepository** protocol and a **CacheBackedContextStore** that uses it. Use them when you want session-level context to be persisted in a database (e.g. Postgres) with an optional cache layer (e.g. Redis or in-memory) for fast reads.

---

## DbRepository (protocol)

`DbRepository` is a **protocol** (interface) for persisting context by `context_key`. Implementations are **domain-specific** and live in the consuming agent repo; the shared-lib only depends on this interface.

### Interface

| Method | Description |
|--------|-------------|
| `get(context_key: str) -> dict[str, Any] \| None` | Return stored data for `context_key`, or `None` if not found. |
| `set(context_key: str, data: Mapping[str, Any]) -> None` | Persist data for `context_key` (upsert semantics). |
| `delete(context_key: str) -> None` | Remove stored data for `context_key`. |

- `data` is a JSON-serializable mapping (e.g. `{"user_name": "alice", "repo_name": "my-repo"}`).
- Your implementation can restrict which keys are persisted and how they map to your schema.

### Implementing DbRepository

1. Create a class that implements `get`, `set`, and `delete` with the same signatures.
2. Use your own persistence (e.g. SQLAlchemy, asyncpg). The shared-lib does not depend on any particular DB library.

**Example (SQLAlchemy + Postgres):**

```python
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from autobots_devtools_shared_lib.common.services.context import DbRepository


class MyContextRepository:
    """Implements DbRepository using SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, context_key: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            entity = session.get(MyContextEntity, context_key)
            if entity is None:
                return None
            return {"user_name": entity.user_name, "repo_name": entity.repo_name}  # map to dict

    def set(self, context_key: str, data: Mapping[str, Any]) -> None:
        with self._session_factory() as session:
            entity = session.get(MyContextEntity, context_key)
            if entity is None:
                entity = MyContextEntity(context_key=context_key, **data)
                session.add(entity)
            else:
                for k, v in data.items():
                    setattr(entity, k, v)
            session.commit()

    def delete(self, context_key: str) -> None:
        with self._session_factory() as session:
            entity = session.get(MyContextEntity, context_key)
            if entity is not None:
                session.delete(entity)
                session.commit()
```

You need your own ORM model and table (e.g. `MyContextEntity` with `context_key` as primary key and columns for the fields you persist).

---

## CacheBackedContextStore

`CacheBackedContextStore` is a **write-through** store: the database (via `DbRepository`) is the source of truth; the cache is used for fast reads.

### Behaviour

| Operation | Behaviour |
|-----------|-----------|
| **get** | Cache hit → return cached value. Cache miss → load from DB, write to cache, return. |
| **set** | Write to DB, then write to cache. |
| **update** | Read current from DB (not cache), merge patch, write to DB, then write to cache. |
| **delete** | Delete from DB, then delete from cache. |

So: every write goes to the DB first; the cache is kept in sync. Reads use the cache when possible to avoid hitting the DB every time.

### Constructor

```python
from autobots_devtools_shared_lib.common.services.context import (
    CacheBackedContextStore,
    ContextStore,
    DbRepository,
    InMemoryContextStore,
)

store = CacheBackedContextStore(db=my_db_repository, cache=some_context_store)
```

- **db**: Your `DbRepository` implementation (e.g. Postgres-backed).
- **cache**: Any `ContextStore` implementation. Typical choices:
  - **InMemoryContextStore()** — simple, no extra infra; suitable for single-process / dev.
  - **RedisContextStore(config)** — for multi-process or production when you have Redis.

### Using the store in the app

1. **Build the store at startup** (after loading settings and DB engine):

   ```python
   from autobots_devtools_shared_lib.common.services import (
       CacheBackedContextStore,
       InMemoryContextStore,
       set_context_store,
   )

   repo = MyContextRepository(session_factory)
   cache = InMemoryContextStore()  # or RedisContextStore(...) if you have Redis
   set_context_store(CacheBackedContextStore(db=repo, cache=cache))
   ```

2. **Get the store where you need it**:

   ```python
   from autobots_devtools_shared_lib.common.services import get_context_store

   store = get_context_store()
   store.set("session-123", {"user_name": "alice", "repo_name": "my-repo"})
   data = store.get("session-123")
   store.update("session-123", {"jira_number": "PROJ-42"})
   store.delete("session-123")
   ```

If you never call `set_context_store()`, `get_context_store()` falls back to the default behaviour (e.g. InMemoryContextStore when `DYNA_CONTEXT_CONFIG_PATH` is not set). So you only need to wire `CacheBackedContextStore` when you want DB-backed context with optional Redis cache.

---

## Summary

| Piece | Role |
|-------|------|
| **DbRepository** | Protocol you implement in your repo to persist context in your DB (e.g. Postgres). |
| **CacheBackedContextStore** | Uses your DbRepository as source of truth and a ContextStore as cache; exposes `get` / `set` / `update` / `delete`. |
| **set_context_store** | Registers the store (e.g. a `CacheBackedContextStore`) for the process. |
| **get_context_store** | Returns the registered store for use in handlers/tools. |

Implement `DbRepository` in your agent repo, then construct `CacheBackedContextStore(db=repo, cache=...)` and pass it to `set_context_store()` at startup.

---

## Context key resolver

Use-case apps can control how the **context store key** is derived from agent state by setting a **context key resolver**. Register it at app startup (before creating the agent) so that `get_context`, `set_context`, and `update_context` use your key.

Define a resolver that takes the current agent state and returns a string key, then pass it to `set_context_key_resolver`:

```python
from collections.abc import Mapping
from typing import Any

from autobots_devtools_shared_lib.common.utils.context_utils import set_context_key_resolver


def _resolve_bro_context_key(state: Mapping[str, Any]) -> str:
    user_name = state.get("user_name") or "default"
    return f"{user_name}"


set_context_key_resolver(_resolve_bro_context_key)
```

If a **context config file** (e.g. `context.yaml`, loaded when `DYNA_CONTEXT_CONFIG_PATH` is set) is present and a **prefix** is defined (e.g. under the `context.redis.prefix` key for the Redis backend), that prefix is automatically prepended to the context key when storing and retrieving. The effective key in the backend is `{prefix}_{context_key}`. Your resolver can therefore return a short key (e.g. `user_name`); the store will namespace it for you.

Ensure any keys you read from `state` (e.g. `user_name`) are present in the agent state: pass them in `input_state` when invoking the agent and add them to the DynAgent state schema if needed.
