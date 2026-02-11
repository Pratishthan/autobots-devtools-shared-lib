"""
Local file server implementing the same REST API as the file server used by fserver_client.
Use for testing list_files, read_file, write_file, move_file, create_download_link.

Run: uvicorn local_file_server.app:app --reload --host 0.0.0.0 --port 9002
Or: make file-server (from autobots-devtools-shared-lib)
"""

import base64
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

FILE_SERVER_ROOT = Path(os.getenv("FILE_SERVER_ROOT", ".")).resolve()

app = FastAPI(
    title="Local File Server",
    description="Test server for fserver_client tools (listFiles, readFile, writeFile, moveFile, createDownloadLink).",
)


class ListFilesBody(BaseModel):
    path: str | None = None
    # workspace fields (ignored by this server but accepted for API compatibility)
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None


class ReadFileBody(BaseModel):
    fileName: str
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None


class WriteFileBody(BaseModel):
    file_name: str
    file_content: str  # base64
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None


class MoveFileBody(BaseModel):
    source_path: str
    destination_path: str
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None


def _safe_path(relative: str) -> Path:
    """Resolve path under FILE_SERVER_ROOT; reject path traversal."""
    if not relative or relative.strip() == "":
        return FILE_SERVER_ROOT
    p = (FILE_SERVER_ROOT / relative.strip().lstrip("/")).resolve()
    try:
        p.resolve().relative_to(FILE_SERVER_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path: outside root") from None
    return p


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check; returns disk_usage for get_disk_usage tool."""
    if not FILE_SERVER_ROOT.exists():
        return {"disk_usage": {"root": str(FILE_SERVER_ROOT), "size_bytes": 0}}
    total = 0
    for _root, _dirs, files in os.walk(FILE_SERVER_ROOT):
        for f in files:
            fp = Path(_root) / f
            if fp.is_file():
                total += fp.stat().st_size
    return {"disk_usage": {"root": str(FILE_SERVER_ROOT), "size_bytes": total}}


@app.post("/listFiles")
def list_files(body: ListFilesBody) -> dict[str, Any]:
    """List files under path (and optional workspace filters; filters ignored here)."""
    base = _safe_path(body.path) if body.path else FILE_SERVER_ROOT
    if not base.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not base.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    files: list[str] = []
    for root, _dirs, filenames in os.walk(base):
        for name in filenames:
            full = Path(root) / name
            try:
                rel = full.relative_to(FILE_SERVER_ROOT)
            except ValueError:
                continue
            files.append(str(rel).replace("\\", "/"))
    return {"files": files}


@app.post("/readFile")
def read_file(body: ReadFileBody) -> Response:
    """Return file content as raw bytes (client decodes UTF-8 or base64)."""
    path = _safe_path(body.fileName)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")
    content = path.read_bytes()
    return Response(content=content, media_type="application/octet-stream")


@app.post("/writeFile")
def write_file(body: WriteFileBody) -> dict[str, Any]:
    """Write base64-encoded content to file."""
    path = _safe_path(body.file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(body.file_content.encode("utf-8"))
    path.write_bytes(raw)
    rel = path.relative_to(FILE_SERVER_ROOT)
    return {"path": str(rel).replace("\\", "/"), "size_bytes": len(raw)}


@app.post("/moveFile")
def move_file(body: MoveFileBody) -> dict[str, Any]:
    """Move file from source_path to destination_path."""
    src = _safe_path(body.source_path)
    dst = _safe_path(body.destination_path)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
    if not src.is_file():
        raise HTTPException(status_code=400, detail="Source is not a file")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    rel = dst.relative_to(FILE_SERVER_ROOT)
    return {
        "message": "OK",
        "destination_path": str(rel).replace("\\", "/"),
        "size_bytes": dst.stat().st_size,
    }


@app.post("/createDownloadLink")
def create_download_link(body: ReadFileBody) -> Response:
    """Return a simple download link (file path) as text for local testing."""
    path = _safe_path(body.fileName)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")
    link = f"file://{path}"
    return Response(content=link.encode("utf-8"), media_type="text/plain; charset=utf-8")
