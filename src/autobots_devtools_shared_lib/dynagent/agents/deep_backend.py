# ABOUTME: Backend registry for the deep engine's virtual filesystem.
# ABOUTME: Resolves deep-agents.yaml default_backend config into deepagents backends.

from collections.abc import Callable
from pathlib import Path
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend, StoreBackend
from deepagents.backends.protocol import BackendProtocol

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.agents.fserver_backend import FileServerBackend

logger = get_logger(__name__)


def _build_state(_cfg: dict[str, Any], **_kw: Any) -> None:
    """deepagents defaults to StateBackend when backend is None."""


def _build_filesystem(cfg: dict[str, Any], **_kw: Any) -> FilesystemBackend:
    root_dir = cfg.get("root_dir")
    if root_dir:
        Path(root_dir).mkdir(parents=True, exist_ok=True)
    return FilesystemBackend(root_dir=root_dir, virtual_mode=True)


def _build_store(_cfg: dict[str, Any], *, store: Any = None, **_kw: Any) -> Any:
    if store is None:
        msg = (
            "Backend type 'store' requires the store= kwarg on create_base_deepagent "
            "(a live BaseStore instance cannot be expressed in YAML)."
        )
        raise ValueError(msg)
    return StoreBackend(store=store)


def _build_fserver(_cfg: dict[str, Any], **_kw: Any) -> Any:
    def factory(_runtime: Any) -> FileServerBackend:
        # session_id/context_key are resolved lazily from ambient ContextVars
        # (set per request by the Chainlit layer); see FileServerBackend._resolve.
        return FileServerBackend()

    return factory


def _build_composite(cfg: dict[str, Any], *, store: Any = None, **_kw: Any) -> Any:
    route_configs = cfg.get("routes") or {}
    built_routes = {
        prefix: _build_backend(route_cfg, store=store)
        for prefix, route_cfg in route_configs.items()
    }

    def factory(runtime: Any) -> CompositeBackend:
        routes: dict[str, BackendProtocol] = {}
        for prefix, backend in built_routes.items():
            if backend is None:
                routes[prefix] = StateBackend()
            elif isinstance(backend, BackendProtocol):
                routes[prefix] = backend
            else:  # BackendFactory route (e.g. fserver): materialize per runtime
                routes[prefix] = backend(runtime)
        return CompositeBackend(default=StateBackend(), routes=routes)

    return factory


_BACKEND_REGISTRY: dict[str, Callable[..., Any]] = {
    "state": _build_state,
    "filesystem": _build_filesystem,
    "fserver": _build_fserver,
    "store": _build_store,
    "composite": _build_composite,
}


def _build_backend(cfg: dict[str, Any], *, store: Any = None) -> Any:
    backend_type = cfg.get("type", "state")
    builder = _BACKEND_REGISTRY.get(backend_type)
    if builder is None:
        msg = f"Unknown backend type '{backend_type}'. Valid types: {sorted(_BACKEND_REGISTRY)}"
        raise ValueError(msg)
    return builder(cfg, store=store)


def resolve_backend(
    backend_config: dict[str, Any] | None,
    override: Any = None,
    store: Any = None,
) -> Any:
    """Resolve the domain backend; an explicit backend= kwarg wins over YAML."""
    if override is not None:
        return override
    if not backend_config:
        return None
    backend = _build_backend(backend_config, store=store)
    logger.info(f"resolve_backend: type={backend_config.get('type', 'state')}")
    return backend
