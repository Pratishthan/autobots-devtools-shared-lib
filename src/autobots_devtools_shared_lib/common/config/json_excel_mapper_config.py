# ABOUTME: Pydantic models and loader for JSON ↔ Excel mapper configuration.
# ABOUTME: Mapper defines columns (header + path), optional rowSourcePath, optional refMode.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ColumnConfig(BaseModel):
    """Single column mapping: header name and path into the row object."""

    header: str = Field(..., description="Excel column header")
    path: str = Field(..., description="Dot-path into the row object (e.g. id, type, $key, $key/type); ignored when type is serial")
    type: Literal["array", "serial", "gen-sl"] | None = Field(
        default=None,
        description="array: value as array (join/dump). serial or gen-sl: generated 1-based row number in Excel; ignored on Excel→JSON",
    )
    elementType: Literal["string", "number", "boolean"] | None = Field(
        default=None,
        description="Hint for array elements",
    )
    delimiter: str = Field(
        default=",",
        description="Used when type is array (primitive)",
    )


class MapperConfig(BaseModel):
    """Mapper configuration for JSON ↔ Excel conversion."""

    columns: list[ColumnConfig] = Field(..., description="Header name + path per column")
    rowSourcePath: str | None = Field(
        default=None,
        description="When set, rows come from the object at this path (e.g. schema properties)",
    )
    refMode: Literal["inline", "uniqueSheet", "perOccurrenceSheet", "parentOnly"] = Field(
        default="inline",
        description="How to handle $ref and non-primitive arrays when using rowSourcePath",
    )


def load_mapper_config(
    mapper_name: str,
    mapper_base_path: str | Path | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
) -> MapperConfig:
    """Load mapper configuration by name from base path (file server or local).

    Args:
        mapper_name: Name of the mapper (e.g. 'PymtBankParam'); file is {mapper_name}.json
        mapper_base_path: Directory containing mapper JSON files. If None, use env JSON_EXCEL_MAPPER_PATH.
        workspace_context: Optional JSON string for workspace (e.g. '{"workspace_base_path": "..."}').
                          When non-empty, load via file server read_file.
        session_id: Optional session ID for file server calls.

    Returns:
        Validated MapperConfig.

    Raises:
        FileNotFoundError: If mapper file not found.
        json.JSONDecodeError: If file is invalid JSON.
        pydantic.ValidationError: If JSON does not match MapperConfig schema.
    """
    base = mapper_base_path
    if base is None:
        base = os.environ.get("JSON_EXCEL_MAPPER_PATH")
    if base is None:
        msg = "mapper_base_path or JSON_EXCEL_MAPPER_PATH must be set to load mapper by name"
        raise ValueError(msg)

    name = mapper_name if mapper_name.endswith(".json") else f"{mapper_name}.json"
    if isinstance(base, str):
        base_str = base.rstrip("/")
        file_path = f"{base_str}/{name}" if base_str else name
    else:
        file_path = Path(base) / name

    workspace = workspace_context.strip()
    if workspace and workspace != "{}":
        try:
            from autobots_devtools_shared_lib.common.utils.fserver_client_utils import read_file
        except ImportError:
            pass
        else:
            try:
                ctx = json.loads(workspace) if workspace.startswith("{") else {}
            except json.JSONDecodeError:
                ctx = {}
            ws_str = json.dumps(ctx) if isinstance(ctx, dict) else "{}"
            rel_path = str(file_path) if isinstance(file_path, Path) else file_path
            content = read_file(rel_path, workspace_context=ws_str, session_id=session_id)
            if content.startswith("Error ") or content.startswith("HTTP"):
                raise FileNotFoundError(f"Mapper file not found or read failed: {content[:200]}")
            raw = json.loads(content)
            return MapperConfig.model_validate(raw)

    path = Path(file_path) if not isinstance(file_path, Path) else file_path
    if not path.exists():
        raise FileNotFoundError(f"Mapper file not found: {path}")
    raw = json.loads(path.read_text())
    return MapperConfig.model_validate(raw)
