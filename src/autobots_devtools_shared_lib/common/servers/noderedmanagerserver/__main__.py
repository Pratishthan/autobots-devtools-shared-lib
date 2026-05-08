"""Entry point: reads host/port from node-red-config.yaml and starts the server."""

import asyncio
import sys

import uvicorn

from autobots_devtools_shared_lib.common.servers.noderedmanagerserver.config import (
    NodeRedManagerServerConfig,
)

# asyncio.create_subprocess_exec requires ProactorEventLoop on Windows.
# Python 3.12+ defaults to it, but set explicitly to guard against uvicorn
# or dependency changes that could reset the event loop policy.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    cfg = NodeRedManagerServerConfig()
    uvicorn.run(
        "autobots_devtools_shared_lib.common.servers.noderedmanagerserver.app:app",
        host=cfg.node_red_manager_server_host,
        port=cfg.node_red_manager_server_port,
        reload=False,
    )
