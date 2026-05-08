"""Domain exceptions for the Node-RED instance manager server."""


class NodeRedManagerError(Exception):
    """Base exception for Node-RED instance manager errors.

    Subclasses declare a status_code so the central FastAPI exception handler
    can convert them to HTTP responses without any per-endpoint boilerplate.

    ERROR_CODE is a stable string constant included in HTTP responses and utils
    error strings so consumers can distinguish error types without re-raising:

        from ...exceptions import FlowsFileNotFoundError
        result = create_instance(...)
        if FlowsFileNotFoundError.ERROR_CODE in result:
            ...
    """

    status_code: int = 500
    ERROR_CODE: str = "NODE_RED_MANAGER_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidWorkspacePathError(NodeRedManagerError):
    """Raised when workspace_base_path is empty or contains invalid path segments."""

    status_code = 400
    ERROR_CODE = "INVALID_WORKSPACE_PATH"


class UnknownEnvironmentError(NodeRedManagerError):
    """Raised when the requested environment name is not in the server config."""

    status_code = 400
    ERROR_CODE = "UNKNOWN_ENVIRONMENT"


class FlowsFileNotFoundError(NodeRedManagerError):
    """Raised when flows.json does not exist at the resolved workspace path."""

    status_code = 404
    ERROR_CODE = "FLOWS_FILE_NOT_FOUND"


class NoAvailablePortError(NodeRedManagerError):
    """Raised when no free port exists within the environment's configured range."""

    status_code = 503
    ERROR_CODE = "NO_AVAILABLE_PORT"


class NodeRedLaunchError(NodeRedManagerError):
    """Raised when the node-red subprocess fails to start."""

    status_code = 500
    ERROR_CODE = "NODE_RED_LAUNCH_ERROR"


class InstanceNotFoundError(NodeRedManagerError):
    """Raised when the requested instance ID is not in the registry."""

    status_code = 404
    ERROR_CODE = "INSTANCE_NOT_FOUND"
