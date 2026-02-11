# Local File Server

Minimal REST server that implements the same API as the file server used by `fserver_client` (listFiles, readFile, writeFile, moveFile, createDownloadLink, health). Use it to test the file server tools against a real backend without a shared environment.

## Setup

From the repo root (or `autobots-devtools-shared-lib`):

```bash
pip install -r autobots-devtools-shared-lib/local_file_server/requirements-file-server.txt
```

Or from `autobots-devtools-shared-lib`:

```bash
pip install -r local_file_server/requirements-file-server.txt
```

## Run

From `autobots-devtools-shared-lib`:

```bash
make file-server
```

Or with uvicorn directly (port 9002 is the default used by `fserver_client`):

```bash
uvicorn local_file_server.app:app --reload --host 0.0.0.0 --port 9002
```

Optional env:

- `FILE_SERVER_ROOT` – directory to serve (default: current directory). Use an empty test dir, e.g. `./.file_server_workspace`.
- `FILE_SERVER_PORT` – port (default 9002); when using `make file-server` you can override: `make file-server FILE_SERVER_PORT=9003`.

## Test the client tools

With the server running and `FILE_SERVER_HOST=localhost` (or unset, since localhost is the default):

```python
from autobots_devtools_shared_lib.dynagent.workspace import Workspace
from autobots_devtools_shared_lib.dynagent.tools.fserver_client import (
    list_files,
    read_file,
    write_file,
    get_disk_usage,
)

# Optional workspace context (any product-specific keys)
ws = Workspace(
    agent_name="my-agent",
    user_name="dev",
    repo_name="my-repo",
    jira_number="JIRA-1",
).to_json()

# Or from env: ws = Workspace.from_env().to_json()

write_file.invoke({"file_name": "hello.txt", "content": "Hello world", "workspace_context": ws})
print(list_files.invoke({"base_path": "", "workspace_context": ws}))
print(read_file.invoke({"file_name": "hello.txt", "workspace_context": ws}))
print(get_disk_usage.invoke({}))
```
