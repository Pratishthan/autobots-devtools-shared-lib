# ABOUTME: deepagents BackendProtocol implementation on the MER file-server sidecar.
# ABOUTME: Direct ls/read/write/upload/download; edit/glob/grep are emulated client-side.

import base64
import fnmatch
from collections.abc import Mapping
from typing import Any

import httpx
from deepagents.backends.protocol import (
    FILE_NOT_FOUND,
    BackendProtocol,
    EditResult,
    FileData,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GlobResult,
    GrepMatch,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)

from autobots_devtools_shared_lib.common.observability import get_logger
from autobots_devtools_shared_lib.common.utils.fserver_client_utils import (
    raw_list_files,
    raw_read_file,
    raw_write_file,
)

logger = get_logger(__name__)

_WORKSPACE_CONTEXT_KEYS = ("agent_name", "user_name", "repo_name", "jira_number")


def workspace_context_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build the sidecar workspace_context dict from runtime state keys."""
    return {key: state[key] for key in _WORKSPACE_CONTEXT_KEYS if state.get(key)}


def _to_server_path(path: str) -> str:
    """Virtual paths are absolute; the sidecar wants workspace-relative paths."""
    return path.lstrip("/")


def _to_virtual_path(path: str) -> str:
    return "/" + path.lstrip("/")


class FileServerBackend(BackendProtocol):
    """Virtual filesystem backed by the file-server sidecar (per-session workspace)."""

    def __init__(
        self,
        session_id: str | None = None,
        workspace_context: dict[str, Any] | None = None,
    ) -> None:
        self._session_id = session_id
        self._workspace_context = dict(workspace_context or {})

    # -- helpers -----------------------------------------------------------

    def _list_all(self) -> list[str]:
        files = raw_list_files("", self._workspace_context, self._session_id)
        return [str(f) for f in files]

    def _read_bytes(self, file_path: str) -> bytes:
        return raw_read_file(_to_server_path(file_path), self._workspace_context, self._session_id)

    def _write_bytes(self, file_path: str, content: bytes) -> None:
        raw_write_file(
            _to_server_path(file_path), content, self._workspace_context, self._session_id
        )

    # -- direct methods ----------------------------------------------------

    def ls(self, path: str) -> LsResult:
        try:
            files = self._list_all()
        except httpx.HTTPError as e:
            return LsResult(error=f"Error listing files: {e}")
        normalized = path if path.endswith("/") else path + "/"
        entries: list[FileInfo] = []
        subdirs: set[str] = set()
        for name in files:
            virtual = _to_virtual_path(name)
            if not virtual.startswith(normalized):
                continue
            relative = virtual[len(normalized) :]
            if "/" in relative:
                subdirs.add(normalized + relative.split("/", 1)[0] + "/")
            else:
                entries.append(FileInfo(path=virtual))
        entries.extend(FileInfo(path=subdir, is_dir=True) for subdir in sorted(subdirs))
        return LsResult(entries=entries)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        try:
            content = self._read_bytes(file_path)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ReadResult(error=f"File '{file_path}' not found")
            return ReadResult(
                error=f"Error reading file '{file_path}': HTTP {e.response.status_code}"
            )
        except httpx.HTTPError as e:
            return ReadResult(error=f"Error reading file '{file_path}': {e}")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            encoded = base64.b64encode(content).decode("utf-8")
            return ReadResult(file_data=FileData(content=encoded, encoding="base64"))
        window = "\n".join(text.split("\n")[offset : offset + limit])
        return ReadResult(file_data=FileData(content=window, encoding="utf-8"))

    def write(self, file_path: str, content: str) -> WriteResult:
        try:
            self._read_bytes(file_path)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                return WriteResult(
                    error=f"Error writing file '{file_path}': HTTP {e.response.status_code}"
                )
        except httpx.HTTPError as e:
            return WriteResult(error=f"Error writing file '{file_path}': {e}")
        else:
            return WriteResult(
                error=(
                    f"Cannot write to {file_path} because it already exists. "
                    "Read and then make an edit, or write to a new path."
                )
            )
        try:
            self._write_bytes(file_path, content.encode("utf-8"))
        except httpx.HTTPError as e:
            return WriteResult(error=f"Error writing file '{file_path}': {e}")
        return WriteResult(path=file_path)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                self._write_bytes(path, content)
                responses.append(FileUploadResponse(path=path))
            except httpx.HTTPError as e:
                responses.append(FileUploadResponse(path=path, error=str(e)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                responses.append(FileDownloadResponse(path=path, content=self._read_bytes(path)))
            except httpx.HTTPStatusError as e:
                error = FILE_NOT_FOUND if e.response.status_code == 404 else str(e)
                responses.append(FileDownloadResponse(path=path, error=error))
            except httpx.HTTPError as e:
                responses.append(FileDownloadResponse(path=path, error=str(e)))
        return responses

    # -- emulated methods (no sidecar endpoints; see spec §4) ----------------

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        try:
            content_bytes = self._read_bytes(file_path)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return EditResult(error=f"File '{file_path}' not found")
            return EditResult(
                error=f"Error editing file '{file_path}': HTTP {e.response.status_code}"
            )
        except httpx.HTTPError as e:
            return EditResult(error=f"Error editing file '{file_path}': {e}")
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return EditResult(error=f"Cannot edit binary file '{file_path}'")

        occurrences = content.count(old_string)
        if occurrences == 0:
            return EditResult(error=f"String not found in file '{file_path}': '{old_string}'")
        if occurrences > 1 and not replace_all:
            return EditResult(
                error=(
                    f"String '{old_string}' appears {occurrences} times in '{file_path}'. "
                    "Use replace_all=True, or provide a more specific string."
                )
            )
        replaced = (
            content.replace(old_string, new_string)
            if replace_all
            else content.replace(old_string, new_string, 1)
        )
        try:
            self._write_bytes(file_path, replaced.encode("utf-8"))
        except httpx.HTTPError as e:
            return EditResult(error=f"Error editing file '{file_path}': {e}")
        return EditResult(path=file_path, occurrences=occurrences if replace_all else 1)

    def _files_under(self, base: str) -> list[str]:
        normalized = base if base.endswith("/") else base + "/"
        return [
            _to_virtual_path(name)
            for name in self._list_all()
            if _to_virtual_path(name).startswith(normalized)
        ]

    @staticmethod
    def _matches_glob(virtual: str, base: str, pattern: str) -> bool:
        normalized = base if base.endswith("/") else base + "/"
        relative = virtual[len(normalized) :]
        # If pattern doesn't contain "/" or "**", it should only match files at current level.
        # This prevents fnmatch's "*" from matching "/" across directory boundaries.
        if "/" not in pattern and "**" not in pattern and "/" in relative:
            return False
        return fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(virtual, pattern)

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        base = path or "/"
        try:
            candidates = self._files_under(base)
        except httpx.HTTPError as e:
            return GlobResult(error=f"Error listing files: {e}")
        matches = [
            FileInfo(path=virtual)
            for virtual in candidates
            if self._matches_glob(virtual, base, pattern)
        ]
        return GlobResult(matches=matches)

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> GrepResult:
        base = path or "/"
        try:
            candidates = self._files_under(base)
        except httpx.HTTPError as e:
            return GrepResult(error=f"Error listing files: {e}")
        matches: list[GrepMatch] = []
        for virtual in candidates:
            if glob and not self._matches_glob(virtual, base, glob):
                continue
            try:
                text = self._read_bytes(virtual).decode("utf-8")
            except (httpx.HTTPError, UnicodeDecodeError):
                continue  # unreadable or binary: skip, matching ripgrep behavior
            for line_number, line in enumerate(text.split("\n"), start=1):
                if pattern in line:
                    matches.append(GrepMatch(path=virtual, line=line_number, text=line))
        return GrepResult(matches=matches)
