"""Pydantic request/response models for the file server API. Includes validation for production safety."""

import base64
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _validate_no_path_traversal(v: str) -> str:
    """Reject '..' to prevent directory traversal."""
    if ".." in v:
        raise ValueError("Path cannot contain '..'")
    return v.strip() if v else v


class ListFilesBody(BaseModel):
    path: str | None = None
    workspace_context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Workspace scoping context. Must include `workspace_base_path` to scope file "
            "operations under `<config.root>/<workspace_base_path>`."
        ),
        json_schema_extra={
            "examples": [{"workspace_base_path": "shruthi/fbp-core-genai-sanity-MER-00001"}]
        },
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional session/conversation ID for trace correlation/logging.",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str | None) -> str | None:
        if v is not None and ".." in v:
            raise ValueError("path cannot contain '..'")
        return v.strip() if v else v


class ReadFileBody(BaseModel):
    fileName: str
    workspace_context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Workspace scoping context. Must include `workspace_base_path` to scope file "
            "operations under `<config.root>/<workspace_base_path>`."
        ),
        json_schema_extra={
            "examples": [{"workspace_base_path": "shruthi/fbp-core-genai-sanity-MER-00001"}]
        },
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional session/conversation ID for trace correlation/logging.",
    )

    @field_validator("fileName")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("fileName cannot be empty")
        return _validate_no_path_traversal(v)


class WriteFileBody(BaseModel):
    file_name: str
    file_content: str  # base64
    workspace_context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Workspace scoping context. Must include `workspace_base_path` to scope file "
            "operations under `<config.root>/<workspace_base_path>`."
        ),
        json_schema_extra={
            "examples": [{"workspace_base_path": "shruthi/fbp-core-genai-sanity-MER-00001"}]
        },
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional session/conversation ID for trace correlation/logging.",
    )

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


class MoveFileBody(BaseModel):
    source_path: str
    destination_path: str
    workspace_context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Workspace scoping context. Must include `workspace_base_path` to scope file "
            "operations under `<config.root>/<workspace_base_path>`."
        ),
        json_schema_extra={
            "examples": [{"workspace_base_path": "shruthi/fbp-core-genai-sanity-MER-00001"}]
        },
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional session/conversation ID for trace correlation/logging.",
    )

    @field_validator("source_path", "destination_path")
    @classmethod
    def validate_paths(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        return _validate_no_path_traversal(v)
