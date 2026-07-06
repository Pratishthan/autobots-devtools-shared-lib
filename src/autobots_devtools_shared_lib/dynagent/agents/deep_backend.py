# ABOUTME: Backend registry for the deep engine's virtual filesystem.
# ABOUTME: Resolves deep-agents.yaml default_backend config into deepagents backends.

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend, StoreBackend

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.dynagent.agents.fserver_backend import FileServerBackend

if TYPE_CHECKING:
    from deepagents.backends.protocol import BackendProtocol

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


def _build_fserver(_cfg: dict[str, Any], **_kw: Any) -> FileServerBackend:
    return FileServerBackend()


def _build_composite(cfg: dict[str, Any], *, store: Any = None, **_kw: Any) -> CompositeBackend:
    route_configs = cfg.get("routes") or {}
    routes: dict[str, BackendProtocol] = {}
    for prefix, route_cfg in route_configs.items():
        backend = _build_backend(route_cfg, store=store)
        # _build_state returns None (deepagents' StateBackend default); every other
        # builder returns a BackendProtocol instance.
        routes[prefix] = backend if backend is not None else StateBackend()
    return CompositeBackend(default=StateBackend(), routes=routes)


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
