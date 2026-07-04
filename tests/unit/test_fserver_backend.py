# ABOUTME: Unit tests for FileServerBackend direct methods against faked raw functions.
# ABOUTME: Covers ls windowing, read slicing/binary, write-exists semantics, batch up/download.

import base64

import httpx
import pytest

import autobots_devtools_shared_lib.dynagent.agents.fserver_backend as fb
from autobots_devtools_shared_lib.dynagent.agents.fserver_backend import (
    FileServerBackend,
    workspace_context_from_state,
)


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://fs/x")
    response = httpx.Response(status, request=request, text="err")
    return httpx.HTTPStatusError("boom", request=request, response=response)


@pytest.fixture
def fake_store(monkeypatch):
    """In-memory dict standing in for the sidecar, wired through the raw functions."""
    store: dict[str, bytes] = {}

    def fake_list(base_path="", workspace_context=None, session_id=None):
        return sorted(store)

    def fake_read(file_name, workspace_context=None, session_id=None):
        if file_name not in store:
            raise _http_error(404)
        return store[file_name]

    def fake_write(file_name, content, workspace_context=None, session_id=None):
        store[file_name] = content
        return {"path": file_name, "size_bytes": len(content)}

    monkeypatch.setattr(fb, "raw_list_files", fake_list)
    monkeypatch.setattr(fb, "raw_read_file", fake_read)
    monkeypatch.setattr(fb, "raw_write_file", fake_write)
    return store


def test_workspace_context_from_state_picks_known_keys():
    state = {"session_id": "s", "jira_number": "J-1", "repo_name": "r", "other": "x"}
    assert workspace_context_from_state(state) == {"jira_number": "J-1", "repo_name": "r"}


def test_ls_lists_direct_children_and_subdirs(fake_store):
    fake_store["a.txt"] = b"x"
    fake_store["docs/b.txt"] = b"y"
    fake_store["docs/deep/c.txt"] = b"z"
    result = FileServerBackend().ls("/")
    assert result.error is None
    paths = {e["path"] for e in result.entries}
    assert paths == {"/a.txt", "/docs/"}
    result = FileServerBackend().ls("/docs/")
    paths = {e["path"] for e in result.entries}
    assert paths == {"/docs/b.txt", "/docs/deep/"}


def test_read_returns_utf8_file_data(fake_store):
    fake_store["a.txt"] = b"line1\nline2\nline3"
    result = FileServerBackend().read("/a.txt")
    assert result.error is None
    assert result.file_data["encoding"] == "utf-8"
    assert result.file_data["content"] == "line1\nline2\nline3"


def test_read_applies_offset_and_limit(fake_store):
    fake_store["a.txt"] = b"l1\nl2\nl3\nl4"
    result = FileServerBackend().read("/a.txt", offset=1, limit=2)
    assert result.file_data["content"] == "l2\nl3"


def test_read_binary_returns_base64(fake_store):
    payload = b"\x89PNG\x0d\x0a"
    fake_store["img.png"] = payload
    result = FileServerBackend().read("/img.png")
    assert result.file_data["encoding"] == "base64"
    assert base64.b64decode(result.file_data["content"]) == payload


def test_read_missing_file_returns_error(fake_store):
    result = FileServerBackend().read("/nope.txt")
    assert result.error == "File '/nope.txt' not found"


def test_write_new_file_succeeds(fake_store):
    result = FileServerBackend().write("/new.txt", "hello")
    assert result.error is None
    assert result.path == "/new.txt"
    assert fake_store["new.txt"] == b"hello"


def test_write_existing_file_errors(fake_store):
    fake_store["a.txt"] = b"old"
    result = FileServerBackend().write("/a.txt", "new")
    assert result.error is not None
    assert "already exists" in result.error
    assert fake_store["a.txt"] == b"old"


def test_upload_and_download_files(fake_store):
    backend = FileServerBackend()
    uploads = backend.upload_files([("/u1.txt", b"one"), ("/u2.txt", b"two")])
    assert [u.error for u in uploads] == [None, None]
    downloads = backend.download_files(["/u1.txt", "/missing.txt"])
    assert downloads[0].content == b"one"
    assert downloads[1].error == "file_not_found"


def test_session_and_context_forwarded(monkeypatch):
    seen = {}

    def fake_list(base_path="", workspace_context=None, session_id=None):
        seen["workspace_context"] = workspace_context
        seen["session_id"] = session_id
        return []

    monkeypatch.setattr(fb, "raw_list_files", fake_list)
    FileServerBackend(session_id="s1", workspace_context={"jira_number": "J-1"}).ls("/")
    assert seen == {"workspace_context": {"jira_number": "J-1"}, "session_id": "s1"}
