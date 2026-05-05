"""Entry point: reads host/port from node-red-config.yaml and starts the server."""

import uvicorn

from autobots_devtools_shared_lib.common.servers.noderedmanagerserver.config import (
    NodeRedManagerServerConfig,
)

if __name__ == "__main__":
    cfg = NodeRedManagerServerConfig()
    uvicorn.run(
        "autobots_devtools_shared_lib.common.servers.noderedmanagerserver.app:app",
        host=cfg.node_red_manager_server_host,
        port=cfg.node_red_manager_server_port,
        reload=True,
    )
