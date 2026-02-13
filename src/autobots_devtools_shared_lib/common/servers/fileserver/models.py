"""Pydantic request/response models for the file server API. Includes validation for production safety."""

import base64
from typing import Any

from pydantic import BaseModel, field_validator


def _validate_no_path_traversal(v: str) -> str:
    """Reject '..' to prevent directory traversal."""
    if ".." in v:
        raise ValueError("Path cannot contain '..'")
    return v.strip() if v else v


def _validate_workspace_component(v: str | None) -> str | None:
    """Reject path separators and '..' in workspace components."""
    if v is None:
        return v
    value = v.strip()
    if not value:
        raise ValueError("Workspace component cannot be empty when provided")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError("Workspace components cannot contain path separators or '..'")
    return value


class ListFilesBody(BaseModel):
    path: str | None = None
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None
    conversation_id: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str | None) -> str | None:
        if v is not None and ".." in v:
            raise ValueError("path cannot contain '..'")
        return v.strip() if v else v

    @field_validator("agent_name", "user_name", "repo_name", "jira_number", mode="before")
    @classmethod
    def validate_workspace(cls, v: Any) -> str | None:
        return _validate_workspace_component(v) if isinstance(v, str) else v


class ReadFileBody(BaseModel):
    fileName: str
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None
    conversation_id: str | None = None

    @field_validator("fileName")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("fileName cannot be empty")
        return _validate_no_path_traversal(v)

    @field_validator("agent_name", "user_name", "repo_name", "jira_number", mode="before")
    @classmethod
    def validate_workspace(cls, v: Any) -> str | None:
        return _validate_workspace_component(v) if isinstance(v, str) else v


class WriteFileBody(BaseModel):
    file_name: str
    file_content: str  # base64
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None
    conversation_id: str | None = None

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("file_name cannot be empty")
        return _validate_no_path_traversal(v)

    @field_validator("file_content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v:
            raise ValueError("file_content cannot be empty")
        try:
            base64.b64decode(v)
        except Exception as err:
            raise ValueError("file_content must be valid base64") from err
        return v

    @field_validator("agent_name", "user_name", "repo_name", "jira_number", mode="before")
    @classmethod
    def validate_workspace(cls, v: Any) -> str | None:
        return _validate_workspace_component(v) if isinstance(v, str) else v


class MoveFileBody(BaseModel):
    source_path: str
    destination_path: str
    agent_name: str | None = None
    user_name: str | None = None
    repo_name: str | None = None
    jira_number: str | None = None
    conversation_id: str | None = None

    @field_validator("source_path", "destination_path")
    @classmethod
    def validate_paths(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        return _validate_no_path_traversal(v)

    @field_validator("agent_name", "user_name", "repo_name", "jira_number", mode="before")
    @classmethod
    def validate_workspace(cls, v: Any) -> str | None:
        return _validate_workspace_component(v) if isinstance(v, str) else v
