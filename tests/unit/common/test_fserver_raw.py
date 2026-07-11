# ABOUTME: Unit tests for the raw file-server client layer (bytes/dicts + raised errors).
# ABOUTME: Also locks the tool wrappers' byte-identical success/error strings.

import base64
import json

import httpx
import pytest

import autobots_devtools_shared_lib.common.utils.fserver_client_utils as fs


@pytest.fixture
def mock_server(monkeypatch):
    """Route sidecar POSTs through an httpx.MockTransport; handlers keyed by URL path."""
    handlers: dict = {}

    def _dispatch(request: httpx.Request) -> httpx.Response:
        handler = handlers.get(request.url.path)
        if handler is None:
            return httpx.Response(404, text="no handler")
        return handler(request)

    transport = httpx.MockTransport(_dispatch)
    real_client = httpx.Client
    monkeypatch.setattr(fs.httpx, "Client", lambda **_kwargs: real_client(transport=transport))
    return handlers


def test_raw_list_files_returns_list(mock_server):
    mock_server["/listFiles"] = lambda _req: httpx.Response(
        200, json={"files": ["a.txt", "dir/b.txt"]}
    )
    assert fs.raw_list_files() == ["a.txt", "dir/b.txt"]


def test_raw_list_files_sends_workspace_context(mock_server):
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"files": []})

    mock_server["/listFiles"] = handler
    fs.raw_list_files("sub", {"jira_number": "J-1"}, session_id="s1")
    assert seen["path"] == "sub"
    assert seen["workspace_context"] == {"jira_number": "J-1"}
    assert seen["session_id"] == "s1"


def test_raw_read_file_returns_bytes(mock_server):
    mock_server["/readFile"] = lambda _req: httpx.Response(200, content=b"hello")
    assert fs.raw_read_file("a.txt") == b"hello"


def test_raw_read_file_raises_on_404(mock_server):
    mock_server["/readFile"] = lambda _req: httpx.Response(404, text="not found")
    with pytest.raises(httpx.HTTPStatusError):
        fs.raw_read_file("missing.txt")


def test_raw_write_file_posts_base64_and_returns_result(mock_server):
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"path": "a.txt", "size_bytes": 5})

    mock_server["/writeFile"] = handler
    result = fs.raw_write_file("a.txt", b"hello")
    assert result == {"path": "a.txt", "size_bytes": 5}
    assert base64.b64decode(seen["file_content"]) == b"hello"


def test_raw_create_download_link_returns_bytes(mock_server):
    mock_server["/createDownloadLink"] = lambda _req: httpx.Response(200, content=b"http://dl")
    assert fs.raw_create_download_link("a.txt") == b"http://dl"


# --- wrapper strings stay byte-identical ---


def test_list_files_wrapper_success_string(mock_server):
    mock_server["/listFiles"] = lambda _req: httpx.Response(200, json={"files": ["a.txt"]})
    assert fs.list_files() == "['a.txt']"


def test_read_file_wrapper_error_string(mock_server):
    mock_server["/readFile"] = lambda _req: httpx.Response(404, text="gone")
    assert fs.read_file("x.txt") == "Error reading file: HTTP 404 - gone"


def test_write_file_wrapper_success_string(mock_server):
    mock_server["/writeFile"] = lambda _req: httpx.Response(
        200, json={"path": "a.txt", "size_bytes": 5}
    )
    assert fs.write_file("a.txt", "hello") == ("File written successfully: a.txt, size: 5 bytes")


def test_read_file_wrapper_binary_returns_base64(mock_server):
    mock_server["/readFile"] = lambda _req: httpx.Response(200, content=b"\x89PNG\x0d\x0a")
    assert fs.read_file("img.png") == base64.b64encode(b"\x89PNG\x0d\x0a").decode("utf-8")
