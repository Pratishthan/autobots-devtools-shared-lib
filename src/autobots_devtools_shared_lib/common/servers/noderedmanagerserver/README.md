# Node-RED Instance Manager Server

A FastAPI server that manages dynamic Node-RED instances. It launches instances on demand
using pre-configured templates, assigns them ports from a per-template range, and kills
them on request.

## Overview

Each Node-RED instance is launched as:
```
FLOW=<flows_json_path> node-red -u <template_path> --port <port>
```

Templates are directories containing a `settings.js` and `package.json`, and each template
owns its own port range to avoid conflicts.

## Setup

**Prerequisites:**
- `node-red` binary on `PATH` (or configure `node_red_executable` in the YAML)

```bash
npm install -g node-red
```

**Install the shared lib:**
```bash
pip install -e "autobots-devtools-shared-lib"
```

## Configuration

Create a `node-red-config.yaml` file:

```yaml
# Path to the node-red binary (optional, defaults to "node-red")
node_red_executable: /usr/local/bin/node-red

# Host and port for the manager server itself.
# server_host is also used to build instance URLs — set it to the VM IP or hostname
# if this server runs remotely so callers get the correct URL back.
server_host: 0.0.0.0   # optional, defaults to "0.0.0.0"
server_port: 9003      # optional, defaults to 9003

templates:
  - name: compose-template
    path: /path/to/compose-template
    base_port: 1880
    max_port: 1920

  - name: basic-template
    path: /path/to/basic-template
    base_port: 1921
    max_port: 1980
```

Point the server to the file via env var (defaults to `node-red-config.yaml` in cwd):

```bash
export NODE_RED_CONFIG_FILE=/path/to/node-red-config.yaml
```

### Template Directory Format

Each template directory must contain at minimum:
```
my-template/
├── settings.js     # Node-RED settings (required)
└── package.json    # Node-RED package deps (required)
```

## Run

```bash
# From autobots-devtools-shared-lib (host/port taken from node-red-config.yaml)
make node-red-server

# Or directly
python -m autobots_devtools_shared_lib.common.servers.noderedmanagerserver
```

## Environment Variables

Only one env var remains — everything else is in the YAML:

| Variable | Default | Description |
|---|---|---|
| `NODE_RED_CONFIG_FILE` | `node-red-config.yaml` | Path to the YAML config file |

## API Endpoints

### `GET /health`
Returns server status, running instance count, and available template names.

```bash
curl http://localhost:9003/health
```
```json
{
  "status": "healthy",
  "timestamp": "2026-04-30T10:00:00+00:00",
  "running_instances": 2,
  "available_templates": ["compose-template", "basic-template"]
}
```

---

### `POST /create-instance`
Launch a new Node-RED instance.

```bash
curl -X POST http://localhost:9003/create-instance \
  -H "Content-Type: application/json" \
  -d '{"flows_json_path": "/projects/projectA/flows.json", "template_name": "compose-template"}'
```

**Response (201):**
```json
{
  "id": "3f1a2b4c-...",
  "url": "http://192.168.1.100:1880"
}
```

**Errors:**
- `400` — unknown `template_name` or `flows_json_path` does not exist
- `503` — no ports available in the template's configured range

---

### `POST /kill-instance`
Kill a running Node-RED instance by its id.

```bash
curl -X POST http://localhost:9003/kill-instance \
  -H "Content-Type: application/json" \
  -d '{"id": "3f1a2b4c-..."}'
```

**Response (200):**
```json
{"message": "Instance 3f1a2b4c-... killed successfully"}
```

**Errors:**
- `404` — instance id not found

---

### `GET /instances`
List all currently running instances.

```bash
curl http://localhost:9003/instances
```
```json
{
  "instances": [
    {
      "id": "3f1a2b4c-...",
      "port": 1880,
      "template_name": "compose-template",
      "url": "http://localhost:1880",
      "pid": 12345
    }
  ],
  "count": 1
}
```

---

### `GET /docs`
Interactive Swagger UI.

## Shutdown Behaviour

When the manager server stops, it sends `SIGTERM` to all tracked Node-RED instances
(concurrently). Instances that do not exit within 5 seconds receive `SIGKILL`.
