"""
Node-RED instance manager server.

Manages dynamic Node-RED instances: launch on demand with a chosen template and flows file,
track them in memory, and kill on request.

Templates are configured in a YAML file (default: node-red-config.yaml in cwd):
  NODE_RED_CONFIG_FILE=/path/to/node-red-config.yaml

Run:
  uvicorn autobots_devtools_shared_lib.common.servers.noderedmanagerserver.app:app \
      --reload --host 0.0.0.0 --port 9003
Or: make node-red-server (from autobots-devtools-shared-lib)
"""

import asyncio
import contextlib
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.servers.noderedmanagerserver.config import (
    NodeRedManagerServerConfig,
    TemplateConfig,
)
from autobots_devtools_shared_lib.common.servers.noderedmanagerserver.exceptions import (
    FlowsFileNotFoundError,
    InstanceNotFoundError,
    InvalidWorkspacePathError,
    NoAvailablePortError,
    NodeRedLaunchError,
    NodeRedManagerError,
    UnknownEnvironmentError,
)
from autobots_devtools_shared_lib.common.servers.noderedmanagerserver.models import (
    CreateInstanceRequest,
    CreateInstanceResponse,
    InstanceInfo,
    KillInstanceRequest,
    KillInstanceResponse,
)

logger = get_logger(__name__)
config = NodeRedManagerServerConfig()

# In-memory registry: instance_id -> (InstanceInfo, subprocess handle, TTL task)
_registry: dict[str, tuple[InstanceInfo, asyncio.subprocess.Process, asyncio.Task[None]]] = {}


# ---------------------------------------------------------------------------
# Port scanning
# ---------------------------------------------------------------------------


async def _is_port_available(port: int) -> bool:
    """Return True if nothing is listening on the given TCP port."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=0.1)
    except (ConnectionRefusedError, OSError, TimeoutError):
        return True  # refused / timeout → port is free
    else:
        writer.close()
        await writer.wait_closed()
        return False  # connected → port is in use


async def _find_available_port(template: TemplateConfig) -> int:
    """Scan sequentially within the template's port range; skip ports used by tracked instances."""
    used_ports = {info.port for info, _, _ in _registry.values()}
    for port in range(template.min_port, template.max_port + 1):
        if port in used_ports:
            continue
        if await _is_port_available(port):
            return port
    raise NoAvailablePortError(
        f"No available ports in range [{template.min_port}, {template.max_port}] "
        f"for environment '{template.name}'. All ports are occupied."
    )


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------


async def _launch_node_red(
    template: TemplateConfig, flows_json_path: str, port: int, instance_id: str
) -> asyncio.subprocess.Process:
    """Launch node-red as an async subprocess.

    INSTANCE_ID is passed as an env var so the environment's settings.js can set
    httpAdminRoot and httpNodeRoot to '/<instance_id>' for URL isolation.

    On Windows, node-red is installed as a .cmd batch file and cannot be executed
    directly by create_subprocess_exec — it must be routed through cmd.exe.
    CREATE_NEW_PROCESS_GROUP assigns a new process group so taskkill /T can target
    the entire tree (cmd.exe + node-red child) during cleanup.
    """
    env = {**os.environ, "FLOW": flows_json_path, "INSTANCE_ID": instance_id}
    node_red_args = ["-u", str(template.path), "--port", str(port)]
    if sys.platform == "win32":
        cmd = ["cmd", "/c", config.node_red_executable, *node_red_args]
        extra_kwargs: dict = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        cmd = [config.node_red_executable, *node_red_args]
        extra_kwargs = {}
    return await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **extra_kwargs,
    )


async def _kill_instance(instance_id: str, process: asyncio.subprocess.Process) -> None:
    """Terminate the process and its children.

    On Unix: SIGTERM with a 5s grace period, then SIGKILL.
    On Windows: taskkill /F /T kills the entire process tree (cmd.exe + node-red child)
    because process.terminate() only kills cmd.exe, leaving node-red orphaned.
    """
    try:
        if sys.platform == "win32":
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/F",
                "/T",
                "/PID",
                str(process.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
            await process.wait()
            logger.info("Instance %s terminated (Windows taskkill)", instance_id)
        else:
            process.terminate()  # SIGTERM on Unix
            await asyncio.wait_for(process.wait(), timeout=5.0)
            logger.info("Instance %s terminated gracefully", instance_id)
    except ProcessLookupError:
        logger.info("Instance %s process already gone (pid=%s)", instance_id, process.pid)
    except TimeoutError:
        logger.warning("Instance %s did not terminate in 5s, sending SIGKILL", instance_id)
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()


async def _ttl_kill(instance_id: str, ttl_seconds: int) -> None:
    """Background task: auto-kill an instance after its TTL expires."""
    try:
        await asyncio.sleep(ttl_seconds)
    except asyncio.CancelledError:
        return  # killed manually before TTL; nothing to do
    entry = _registry.pop(instance_id, None)
    if entry is None:
        return  # already removed (e.g. manual kill lost the race)
    _, process, _ = entry
    logger.info("TTL expired for instance %s, killing", instance_id)
    await _kill_instance(instance_id, process)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup: validate config and log. Shutdown: kill all tracked instances."""
    logger.info(
        "Node-RED server starting (host=%s, port=%s, base_path=%s, environments=%s)",
        config.node_red_manager_server_host,
        config.node_red_manager_server_port,
        config.base_path,
        [f"{t.name}[{t.min_port}-{t.max_port}]" for t in config.environments.values()],
    )
    try:
        NodeRedManagerServerConfig.validate()
    except ValueError:
        logger.exception("Node-RED server config invalid")
        raise

    yield

    logger.info("Node-RED server shutting down, terminating %d instance(s)", len(_registry))
    for _, _, ttl_task in _registry.values():
        ttl_task.cancel()
    tasks = [_kill_instance(iid, proc) for iid, (_, proc, _) in _registry.items()]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _registry.clear()
    logger.info("Node-RED server shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Node-RED Instance Manager API",
    description=(
        "Manages dynamic Node-RED instances: launch with a chosen template and flows file, "
        "track in memory, and kill on request."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.exception_handler(NodeRedManagerError)
async def _node_red_manager_error_handler(
    _request: Request, exc: NodeRedManagerError
) -> JSONResponse:
    """Convert domain exceptions to HTTP JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.ERROR_CODE},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_instance_id(workspace_context: dict, environment_name: str) -> str:
    """Validate workspace_base_path and return the scoped instance ID.

    Raises InvalidWorkspacePathError if the path is missing or contains '..'.
    """
    workspace_base_path = (workspace_context.get("workspace_base_path") or "").strip()
    if not workspace_base_path:
        raise InvalidWorkspacePathError(
            "workspace_context.workspace_base_path is required and cannot be empty."
        )
    if ".." in workspace_base_path:
        raise InvalidWorkspacePathError("workspace_base_path cannot contain '..'")
    return f"{environment_name}/{workspace_base_path}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Node-RED Instance Manager API",
        "version": "1.0.0",
        "endpoints": {
            "POST /create-instance": "Launch a Node-RED instance with a template and flows file",
            "POST /kill-instance": "Kill a running Node-RED instance by id",
            "GET /instances": "List all running instances",
            "GET /health": "Health check",
        },
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check; returns status, running instance count, and available templates."""
    logger.info("health called")
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "running_instances": len(_registry),
        "available_environments": list(config.environments.keys()),
    }


@app.get("/instances")
def list_instances() -> dict[str, Any]:
    """List all currently running Node-RED instances."""
    instances = [
        {
            "id": info.id,
            "port": info.port,
            "environment_name": info.environment_name,
            "url": info.url,
            "pid": info.pid,
            "created_at": info.created_at.isoformat(),
            "expires_at": info.expires_at.isoformat(),
        }
        for info, _, _ in _registry.values()
    ]
    return {"instances": instances, "count": len(instances)}


@app.post("/create-instance")
async def create_instance(body: CreateInstanceRequest) -> CreateInstanceResponse:
    """
    Launch a new Node-RED instance.

    Finds the next available port, launches node-red with the given template and flows file,
    registers the instance, and returns its id and URL.
    """
    logger.info(
        "create-instance called environment=%s flows=%s workspace=%s",
        body.environment_name,
        body.flows_json_path,
        body.workspace_context,
    )

    # 1. Validate workspace path and derive scoped instance ID
    instance_id = _resolve_instance_id(body.workspace_context, body.environment_name)

    # 2. Return existing instance if one is already running for this workspace
    if instance_id in _registry:
        existing_info, _, _ = _registry[instance_id]
        logger.info(
            "create-instance reusing existing id=%s url=%s", existing_info.id, existing_info.url
        )
        return CreateInstanceResponse(
            id=existing_info.id, url=existing_info.url, expires_at=existing_info.expires_at
        )

    # 3. Validate environment name
    environment = config.environments.get(body.environment_name)
    if environment is None:
        logger.warning("create-instance unknown environment=%s", body.environment_name)
        raise UnknownEnvironmentError(
            f"Unknown environment '{body.environment_name}'. "
            f"Available: {list(config.environments.keys())}"
        )

    # 4. Resolve full flows path: base_path / workspace_base_path / flows_json_path
    workspace_base_path = instance_id.split("/", 1)[1]
    flows_path = Path(config.base_path) / workspace_base_path / body.flows_json_path
    if not flows_path.exists():
        raise FlowsFileNotFoundError(f"flows.json not found at resolved path: {flows_path}")

    # 5. Find next available port within this environment's port range (raises NoAvailablePortError)
    port = await _find_available_port(environment)

    # 6. Launch subprocess — INSTANCE_ID env var picked up by the environment's settings.js
    try:
        process = await _launch_node_red(environment, str(flows_path), port, instance_id)
    except Exception as e:
        logger.exception("create-instance failed to launch node-red")
        raise NodeRedLaunchError(f"Failed to launch Node-RED: {e!s}") from e

    # 7. Register and return
    ttl = body.ttl_seconds if body.ttl_seconds is not None else config.instance_ttl_seconds
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(seconds=ttl)
    url = f"http://{config.node_red_manager_server_host}:{port}/{instance_id}"
    info = InstanceInfo(
        id=instance_id,
        port=port,
        environment_name=body.environment_name,
        url=url,
        pid=process.pid or 0,
        created_at=created_at,
        expires_at=expires_at,
    )
    ttl_task = asyncio.create_task(_ttl_kill(instance_id, ttl))
    _registry[instance_id] = (info, process, ttl_task)
    logger.info(
        "create-instance success id=%s url=%s pid=%s ttl=%ss", instance_id, url, process.pid, ttl
    )
    return CreateInstanceResponse(id=instance_id, url=url, expires_at=expires_at)


@app.post("/kill-instance")
async def kill_instance(body: KillInstanceRequest) -> KillInstanceResponse:
    """Kill a running Node-RED instance by workspace_base_path."""
    instance_id = _resolve_instance_id(body.workspace_context, body.environment_name)
    logger.info("kill-instance called id=%s", instance_id)

    entry = _registry.get(instance_id)
    if entry is None:
        raise InstanceNotFoundError(f"Instance '{instance_id}' not found")

    _, process, ttl_task = entry
    ttl_task.cancel()
    await _kill_instance(instance_id, process)
    del _registry[instance_id]

    logger.info("kill-instance success id=%s", instance_id)
    return KillInstanceResponse(message=f"Instance {instance_id} killed successfully")
