"""
File server implementing the REST API used by fserver_client.
Suitable for local development and production (open source).

- Local: run with FILE_SERVER_ROOT pointing to a workspace; createDownloadLink returns file://.
- Production: set FILE_SERVER_ENABLE_CORS=1, optional FILE_SERVER_MAX_FILE_SIZE_MB, and
  LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY for OpenTelemetry (traces to Langfuse).

Run: uvicorn autobots_devtools_shared_lib.common.servers.fileserver.app:app --reload --host 0.0.0.0 --port 9002
Or: make file-server (from autobots-devtools-shared-lib)
"""

import base64
import os
import shutil
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from autobots_devtools_shared_lib.common.observability.logging_utils import (
    get_logger,
    set_conversation_id,
)
from autobots_devtools_shared_lib.common.servers.fileserver.config import FileServerConfig
from autobots_devtools_shared_lib.common.servers.fileserver.models import (
    ListFilesBody,
    MoveFileBody,
    ReadFileBody,
    WriteFileBody,
)

logger = get_logger(__name__)
config = FileServerConfig()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup: ensure root exists and log config. Shutdown: log."""
    logger.info("File server starting (root=%s)", config.root)
    FileServerConfig.ensure_root()
    logger.info(
        "CORS=%s, max_file_size_mb=%s",
        config.enable_cors,
        config.max_file_size_mb or "unlimited",
    )
    yield
    logger.info("File server shutting down")


app = FastAPI(
    title="File Server API",
    description="REST API for file operations (listFiles, readFile, writeFile, moveFile, createDownloadLink).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

if config.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _path_under_root(workspace_context: dict[str, Any], relative: str | None) -> Path:
    """Build config.root / workspace_base_path / relative; reject path traversal outside config.root."""
    base = config.root
    workspace_base_path = workspace_context.get("workspace_base_path")
    if workspace_base_path is not None:
        base = (base / str(workspace_base_path)).resolve()
    if not relative or not relative.strip():
        return base
    resolved = (base / relative.strip().lstrip("/")).resolve()
    try:
        resolved.relative_to(config.root)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Path escapes workspace root") from err
    return resolved


@app.get("/")
def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "File Server API",
        "version": "1.0.0",
        "description": "REST API for file storage operations",
        "endpoints": {
            "POST /readFile": "Read file by path",
            "POST /writeFile": "Write file with base64 content",
            "POST /moveFile": "Move file from source to destination",
            "POST /listFiles": "List files in directory",
            "POST /createDownloadLink": "Create a download link for a file",
            "GET /health": "Health check",
        },
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check; returns status and disk_usage (partition usage for get_disk_usage tool)."""
    logger.info("health called")
    if not config.root.exists():
        logger.warning("health: FILE_SERVER_ROOT does not exist, root=%s", config.root)
        return {
            "status": "degraded",
            "timestamp": datetime.now(UTC).isoformat(),
            "disk_usage": {"root": str(config.root), "size_bytes": 0},
        }
    du = shutil.disk_usage(config.root)
    logger.info("health success, root=%s", config.root)
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "disk_usage": {
            "root": str(config.root),
            "size_bytes": du.used,
            "total_bytes": du.total,
            "free_bytes": du.free,
        },
    }


@app.post("/listFiles")
def list_files(body: ListFilesBody) -> dict[str, Any]:
    """List files under path. When workspace_context is set, path is under that workspace."""
    set_conversation_id(body.conversation_id or "default_conversation_id")
    logger.info("listFiles called path=%s", body.path)
    base = _path_under_root(body.workspace_context, body.path)
    if not base.exists():
        logger.warning("listFiles path not found path=%s", base)
        raise HTTPException(status_code=404, detail="Path not found")
    if not base.is_dir():
        logger.warning("listFiles path is not a directory path=%s", base)
        raise HTTPException(status_code=400, detail="Path is not a directory")
    files: list[str] = []
    for root, _dirs, filenames in os.walk(base):
        for name in filenames:
            full = Path(root) / name
            try:
                rel = full.relative_to(config.root)
            except ValueError:
                continue
            files.append(str(rel).replace("\\", "/"))
    logger.info("listFiles success path=%s count=%s", body.path, len(files))
    return {"files": files}


@app.post("/readFile")
def read_file(body: ReadFileBody) -> Response:
    """Return file content as raw bytes. Path resolved under workspace when workspace_context set."""
    set_conversation_id(body.conversation_id or "default_conversation_id")
    logger.info("readFile called fileName=%s", body.fileName)
    path = _path_under_root(body.workspace_context, body.fileName)
    if not path.exists():
        logger.warning("readFile file not found fileName=%s", body.fileName)
        raise HTTPException(status_code=404, detail="File not found")
    if not path.is_file():
        logger.warning("readFile not a file fileName=%s", body.fileName)
        raise HTTPException(status_code=400, detail="Not a file")
    content = path.read_bytes()
    logger.info("readFile success fileName=%s size_bytes=%s", body.fileName, len(content))
    return Response(content=content, media_type="application/octet-stream")


@app.post("/writeFile")
def write_file(body: WriteFileBody) -> dict[str, Any]:
    """Write base64-encoded content to file. Path resolved under workspace when workspace_context set."""
    set_conversation_id(body.conversation_id or "default_conversation_id")
    logger.info("writeFile called file_name=%s", body.file_name)
    try:
        raw = base64.b64decode(body.file_content.encode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 content: {e!s}",
        ) from e
    if config.max_file_size_mb and len(raw) > config.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds limit of {config.max_file_size_mb}MB",
        )
    path = _path_under_root(body.workspace_context, body.file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    rel = path.relative_to(config.root)
    logger.info(
        "writeFile success file_name=%s path=%s size_bytes=%s",
        body.file_name,
        str(rel).replace("\\", "/"),
        len(raw),
    )
    return {"path": str(rel).replace("\\", "/"), "size_bytes": len(raw)}


@app.post("/moveFile")
def move_file(body: MoveFileBody) -> dict[str, Any]:
    """Move file from source_path to destination_path. Paths resolved under workspace when workspace_context set."""
    set_conversation_id(body.conversation_id or "default_conversation_id")
    logger.info(
        "moveFile called source_path=%s destination_path=%s",
        body.source_path,
        body.destination_path,
    )
    src = _path_under_root(body.workspace_context, body.source_path)
    dst = _path_under_root(body.workspace_context, body.destination_path)
    if not src.exists():
        logger.warning("moveFile source not found source_path=%s", body.source_path)
        raise HTTPException(status_code=404, detail="Source file not found")
    if not src.is_file():
        logger.warning("moveFile source is not a file source_path=%s", body.source_path)
        raise HTTPException(status_code=400, detail="Source is not a file")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    rel = dst.relative_to(config.root)
    logger.info(
        "moveFile success destination_path=%s size_bytes=%s",
        str(rel).replace("\\", "/"),
        dst.stat().st_size,
    )
    return {
        "message": "OK",
        "destination_path": str(rel).replace("\\", "/"),
        "size_bytes": dst.stat().st_size,
    }


@app.post("/createDownloadLink")
def create_download_link(body: ReadFileBody) -> Response:
    """Return a simple download link (file path) as text for local testing. Path resolved under workspace when workspace_context set."""
    set_conversation_id(body.conversation_id or "default_conversation_id")
    logger.info("createDownloadLink called fileName=%s", body.fileName)
    path = _path_under_root(body.workspace_context, body.fileName)
    if not path.exists():
        logger.warning("createDownloadLink file not found fileName=%s", body.fileName)
        raise HTTPException(status_code=404, detail="File not found")
    if not path.is_file():
        logger.warning("createDownloadLink not a file fileName=%s", body.fileName)
        raise HTTPException(status_code=400, detail="Not a file")
    link = f"file://{path}"
    logger.info("createDownloadLink success fileName=%s", body.fileName)
    return Response(content=link.encode("utf-8"), media_type="text/plain; charset=utf-8")


if config.langfuse_enabled:
    try:
        from autobots_devtools_shared_lib.common.observability.otel_fastapi import (
            instrument_fastapi,
        )

        if instrument_fastapi(app):
            logger.info("OpenTelemetry instrumentation enabled; traces will be sent to Langfuse.")
        else:
            logger.warning(
                'Langfuse keys set but instrumentation not applied (optional packages missing?). Install: pip install -e ".[file-server,file-server-otel]"'
            )
    except ImportError:
        logger.warning(
            'OpenTelemetry packages not installed. Install with: pip install -e ".[file-server,file-server-otel]"'
        )
