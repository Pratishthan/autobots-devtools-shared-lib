"""
Node-RED instance manager server.

Manages dynamic Node-RED instances: launch on demand with a chosen template and flows file,
track them in memory, and kill on request.

Templates are configured in a YAML file (default: node-red-config.yaml in cwd):
  NODE_RED_CONFIG_FILE=/path/to/node-red-config.yaml

Run:
  uvicorn autobots_devtools_shared_lib.common.servers.noderedserver.app:app \
      --reload --host 0.0.0.0 --port 9003
Or: make node-red-server (from autobots-devtools-shared-lib)
"""

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.servers.noderedserver.config import (
    NodeRedServerConfig,
    TemplateConfig,
)
from autobots_devtools_shared_lib.common.servers.noderedserver.models import (
    CreateInstanceRequest,
    CreateInstanceResponse,
    InstanceInfo,
    KillInstanceRequest,
    KillInstanceResponse,
)

logger = get_logger(__name__)
config = NodeRedServerConfig()

# In-memory registry: instance_id -> (InstanceInfo, subprocess handle)
_registry: dict[str, tuple[InstanceInfo, asyncio.subprocess.Process]] = {}


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
    used_ports = {info.port for info, _ in _registry.values()}
    for port in range(template.min_port, template.max_port + 1):
        if port in used_ports:
            continue
        if await _is_port_available(port):
            return port
    raise RuntimeError(
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
    """
    env = {**os.environ, "FLOW": flows_json_path, "INSTANCE_ID": instance_id}
    return await asyncio.create_subprocess_exec(
        config.node_red_executable,
        "-u",
        str(template.path),
        "--port",
        str(port),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _kill_instance(instance_id: str, process: asyncio.subprocess.Process) -> None:
    """SIGTERM the process; escalate to SIGKILL after 5 seconds."""
    try:
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
        NodeRedServerConfig.validate()
    except ValueError:
        logger.exception("Node-RED server config invalid")
        raise

    yield

    logger.info("Node-RED server shutting down, terminating %d instance(s)", len(_registry))
    tasks = [_kill_instance(iid, proc) for iid, (_, proc) in _registry.items()]
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
        }
        for info, _ in _registry.values()
    ]
    return {"instances": instances, "count": len(instances)}


@app.post("/create-instance", status_code=status.HTTP_201_CREATED)
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

    # 1. Extract and validate workspace_base_path — used as the instance ID
    workspace_base_path: str = (body.workspace_context.get("workspace_base_path") or "").strip()
    if not workspace_base_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_context.workspace_base_path is required and cannot be empty.",
        )
    if ".." in workspace_base_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_base_path cannot contain '..'",
        )
    instance_id = workspace_base_path

    # 2. Reject duplicate — an instance for this workspace is already running
    if instance_id in _registry:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An instance for workspace '{workspace_base_path}' is already running.",
        )

    # 3. Validate environment name
    environment = config.environments.get(body.environment_name)
    if environment is None:
        logger.warning("create-instance unknown environment=%s", body.environment_name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown environment '{body.environment_name}'. "
                f"Available: {list(config.environments.keys())}"
            ),
        )

    # 4. Resolve full flows path: base_path / workspace_base_path / flows_json_path
    flows_path = Path(config.base_path) / workspace_base_path / body.flows_json_path
    if not flows_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"flows.json not found at resolved path: {flows_path}",
        )

    # 5. Find next available port within this environment's port range
    try:
        port = await _find_available_port(environment)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

    # 6. Launch subprocess — INSTANCE_ID env var picked up by the environment's settings.js
    try:
        process = await _launch_node_red(environment, str(flows_path), port, instance_id)
    except Exception as e:
        logger.exception("create-instance failed to launch node-red")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to launch Node-RED: {e!s}",
        ) from e

    # 7. Register and return
    url = f"http://{config.node_red_manager_server_host}:{port}/{instance_id}"
    info = InstanceInfo(
        id=instance_id,
        port=port,
        environment_name=body.environment_name,
        url=url,
        pid=process.pid or 0,
    )
    _registry[instance_id] = (info, process)
    logger.info("create-instance success id=%s url=%s pid=%s", instance_id, url, process.pid)
    return CreateInstanceResponse(id=instance_id, url=url)


@app.post("/kill-instance")
async def kill_instance(body: KillInstanceRequest) -> KillInstanceResponse:
    """Kill a running Node-RED instance by its id."""
    logger.info("kill-instance called id=%s", body.id)

    entry = _registry.get(body.id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance '{body.id}' not found",
        )

    _, process = entry
    await _kill_instance(body.id, process)
    del _registry[body.id]

    logger.info("kill-instance success id=%s", body.id)
    return KillInstanceResponse(message=f"Instance {body.id} killed successfully")
