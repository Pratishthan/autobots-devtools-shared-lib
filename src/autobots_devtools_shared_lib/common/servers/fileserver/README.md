# File Server

REST server that implements the API used by `fserver_client` (listFiles, readFile, writeFile, moveFile, createDownloadLink, health).

## Setup

From the repo root (or `autobots-devtools-shared-lib`):

```bash
pip install -e ".[file-server]"
# With OpenTelemetry (Langfuse): pip install -e ".[file-server,file-server-otel]"
# Or with dev deps: pip install -e ".[dev]"
```

## Run

From `autobots-devtools-shared-lib`:

```bash
make file-server
```

Or with uvicorn directly (port 9002 is the default used by `fserver_client`):

```bash
uvicorn autobots_devtools_shared_lib.common.servers.fileserver.app:app --reload --host 0.0.0.0 --port 9002
```

## Environment (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `FILE_SERVER_ROOT` | `.` | Directory to serve (resolved). |
| `FILE_SERVER_HOST` | `0.0.0.0` | Bind host. |
| `FILE_SERVER_PORT` | `9002` | Bind port. |
| `FILE_SERVER_MAX_FILE_SIZE_MB` | `0` | Max upload size in MB (0 = no limit). |
| `FILE_SERVER_ENABLE_CORS` | (off) | Set to `1` or `true` to enable CORS. |
| `FILE_SERVER_CORS_ORIGINS` | `*` | Comma-separated origins when CORS enabled. |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse project public key; with `LANGFUSE_SECRET_KEY`, traces are sent to Langfuse. |
| `LANGFUSE_SECRET_KEY` | — | Langfuse project secret key. |
| `LANGFUSE_HOST` | - | Langfuse base URL |
| `OTEL_SERVICE_NAME` | `file-server` | Service name shown in Langfuse for this server. |

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set and `opentelemetry-instrumentation-fastapi` is installed (e.g. via `[file-server-otel]`), the app is instrumented and HTTP request traces are sent to Langfuse. `/health` is excluded from spans.

## Tracing (Langfuse)

1. In `.env` set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` (optionally `LANGFUSE_HOST`).
2. Install the OTEL extra into the venv that Make uses: `make install-file-server-otel`.
3. Run: `make file-server-otel`.
4. Send requests to the file server; open your Langfuse project to see traces (service: `file-server`).

If you see a warning about packages not installed, run `make install-file-server-otel` from `autobots-devtools-shared-lib` (Make uses `../.venv`). Spans appear in Langfuse when you send requests (e.g. open http://localhost:9002/docs and call an endpoint).

## Test the client tools

With the server running and `FILE_SERVER_HOST=localhost` (or unset, since localhost is the default):

```python
import json

from autobots_devtools_shared_lib.common.tools.fserver_client_tools import (
    list_files,
    read_file,
    write_file,
    get_disk_usage,
)

# Optional workspace context (any product-specific keys)
workspace_context = json.dumps(
    {
        "agent_name": "my-agent",
        "user_name": "dev",
        "repo_name": "my-repo",
        "jira_number": "JIRA-1",
    }
)

write_file.invoke(
    {"file_name": "hello.txt", "content": "Hello world", "workspace_context": workspace_context}
)
print(list_files.invoke({"base_path": "", "workspace_context": workspace_context}))
print(read_file.invoke({"file_name": "hello.txt", "workspace_context": workspace_context}))
print(get_disk_usage.invoke({}))
```
