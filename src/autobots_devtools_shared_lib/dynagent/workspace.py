"""Generic workspace context for file server and other scoped operations."""

import json
import os
from dataclasses import asdict, dataclass


@dataclass
class Workspace:
    """
    Workspace context for file server tools (list_files, read_file, write_file, etc.).
    Pass as JSON via workspace_context parameter; any field can be None/omitted.
    """

    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None

    @classmethod
    def from_env(cls) -> "Workspace":
        """Build workspace from environment variables (e.g. WORKSPACE_AGENT_NAME)."""
        return cls(
            agent_name=os.getenv("WORKSPACE_AGENT_NAME"),
            user_name=os.getenv("WORKSPACE_USER_NAME"),
            repo_name=os.getenv("WORKSPACE_REPO_NAME"),
            jira_number=os.getenv("WORKSPACE_JIRA_NUMBER"),
        )

    def to_json(self) -> str:
        """JSON string for use as workspace_context in file server tools."""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data)
