"""Pydantic request/response models for the Node-RED instance manager API."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class CreateInstanceRequest(BaseModel):
    workspace_context: dict[str, Any] = Field(
        ...,
        description=(
            "Workspace scoping context. Must include `workspace_base_path` "
            "(e.g. 'userName/repoName-jira'). Used as the instance ID and to resolve "
            "the full flows.json path: base_path/workspace_base_path/flows_json_path."
        ),
        json_schema_extra={"examples": [{"workspace_base_path": "alice/my-project-JIRA-42"}]},
    )
    flows_json_path: str = Field(
        ...,
        description="Relative path to flows.json within the workspace directory.",
    )
    environment_name: str = Field(..., description="Name of the Node-RED environment to use.")

    @field_validator("flows_json_path")
    @classmethod
    def validate_flows_json_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("flows_json_path cannot be empty")
        if ".." in v:
            raise ValueError("flows_json_path cannot contain '..'")
        return v.strip()

    @field_validator("environment_name")
    @classmethod
    def validate_environment_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("environment_name cannot be empty")
        return v.strip()


class CreateInstanceResponse(BaseModel):
    id: str = Field(..., description="Instance ID (workspace_base_path).")
    url: str = Field(..., description="URL to access the Node-RED instance (includes port).")


class KillInstanceRequest(BaseModel):
    id: str = Field(..., description="Instance ID (workspace_base_path) to kill.")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("id cannot be empty")
        return v.strip()


class KillInstanceResponse(BaseModel):
    message: str


class InstanceInfo(BaseModel):
    id: str
    port: int
    environment_name: str
    url: str
    pid: int
