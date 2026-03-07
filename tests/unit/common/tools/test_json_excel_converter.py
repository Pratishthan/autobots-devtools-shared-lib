# Unit tests for JSON ↔ Excel converter (mapper-driven, xlsheets/xlserver).

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from autobots_devtools_shared_lib.common.config.json_excel_mapper_config import (
    ColumnConfig,
    MapperConfig,
    load_mapper_config,
)
from autobots_devtools_shared_lib.common.tools.json_excel_converter import (
    excel_to_json,
    get_value_by_path,
    json_to_dataframes,
    json_to_excel,
    json_to_sheet_data,
    merge_excel_into_json,
    set_value_by_path,
    sheet_data_to_json_shape,
)


# --- Path helpers ---


def test_get_value_by_path_simple():
    obj = {"a": 1, "b": {"c": 2}}
    assert get_value_by_path(obj, "a") == 1
    assert get_value_by_path(obj, "b.c") == 2
    assert get_value_by_path(obj, "missing") is None


def test_get_value_by_path_key_prefix():
    obj = {"$key": "bankName", "type": "string", "description": "Bank Name"}
    assert get_value_by_path(obj, "$key") == "bankName"
    assert get_value_by_path(obj, "$key/type") == "string"
    assert get_value_by_path(obj, "$key/description") == "Bank Name"
    assert get_value_by_path(obj, "type") == "string"


def test_set_value_by_path_simple():
    obj = {}
    set_value_by_path(obj, "a", 1)
    set_value_by_path(obj, "b.c", 2)
    assert obj == {"a": 1, "b": {"c": 2}}


def test_set_value_by_path_key_prefix():
    obj = {}
    set_value_by_path(obj, "$key", "id")
    set_value_by_path(obj, "$key/type", "string")
    assert obj["$key"] == "id"
    assert obj["type"] == "string"


# --- load_mapper_config ---


def test_load_mapper_config_from_file(tmp_path: Path):
    mapper_file = tmp_path / "test_mapper.json"
    mapper_file.write_text(json.dumps({
        "columns": [
            {"header": "Property", "path": "$key"},
            {"header": "Type", "path": "type"},
        ],
        "rowSourcePath": "components.schemas.X.properties",
    }))
    cfg = load_mapper_config("test_mapper", mapper_base_path=str(tmp_path))
    assert cfg.rowSourcePath == "components.schemas.X.properties"
    assert len(cfg.columns) == 2
    assert cfg.columns[0].header == "Property" and cfg.columns[0].path == "$key"


def test_load_mapper_config_adds_json_extension(tmp_path: Path):
    (tmp_path / "mymap.json").write_text(json.dumps({"columns": [{"header": "A", "path": "a"}]}))
    cfg = load_mapper_config("mymap", mapper_base_path=str(tmp_path))
    assert len(cfg.columns) == 1


def test_load_mapper_config_requires_base_path_when_no_env(monkeypatch):
    monkeypatch.delenv("JSON_EXCEL_MAPPER_PATH", raising=False)
    with pytest.raises(ValueError, match="mapper_base_path or JSON_EXCEL_MAPPER_PATH"):
        load_mapper_config("x", mapper_base_path=None)


# --- json_to_sheet_data: list/object ---


def test_json_to_sheet_data_list_of_objects():
    mapper = MapperConfig(columns=[
        ColumnConfig(header="User ID", path="id"),
        ColumnConfig(header="Name", path="name"),
    ])
    data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    result = json_to_sheet_data(data, mapper)
    assert "Sheet1" in result
    rows = result["Sheet1"]
    assert len(rows) == 2
    assert rows[0]["User ID"] == "1" and rows[0]["Name"] == "Alice"
    assert rows[1]["User ID"] == "2" and rows[1]["Name"] == "Bob"


def test_json_to_sheet_data_single_object():
    mapper = MapperConfig(columns=[
        ColumnConfig(header="User ID", path="id"),
        ColumnConfig(header="Phones", path="phones", type="array", elementType="string", delimiter=","),
    ])
    data = {"id": 1, "phones": ["a", "b"]}
    result = json_to_sheet_data(data, mapper)
    assert len(result["Sheet1"]) == 1
    assert result["Sheet1"][0]["Phones"] == "a,b"


def test_json_to_sheet_data_row_source_path():
    mapper = MapperConfig(
        rowSourcePath="components.schemas.PymtBankParam.properties",
        columns=[
            ColumnConfig(header="Property", path="$key"),
            ColumnConfig(header="Type", path="$key/type"),
            ColumnConfig(header="Description", path="$key/description"),
        ],
    )
    data = {
        "components": {
            "schemas": {
                "PymtBankParam": {
                    "properties": {
                        "bankName": {"type": "string", "description": "Bank Name"},
                        "noOfPastDays": {"type": "number", "description": "Past days"},
                    },
                },
            },
        },
    }
    result = json_to_sheet_data(data, mapper)
    assert "Sheet1" in result
    rows = result["Sheet1"]
    assert len(rows) == 2
    assert rows[0]["Property"] == "bankName" and rows[0]["Type"] == "string"
    assert rows[1]["Property"] == "noOfPastDays" and rows[1]["Type"] == "number"


def test_json_to_sheet_data_ref_mode_parent_only():
    mapper = MapperConfig(
        rowSourcePath="components.schemas.X.properties",
        refMode="parentOnly",
        columns=[
            ColumnConfig(header="Property", path="$key"),
            ColumnConfig(header="Type", path="type"),
        ],
    )
    data = {
        "components": {
            "schemas": {
                "X": {
                    "properties": {
                        "addr": {"$ref": "#/components/schemas/Address"},
                    },
                },
            },
        },
    }
    result = json_to_sheet_data(data, mapper)
    assert len(result["Sheet1"]) == 1
    assert result["Sheet1"][0]["Property"] == "addr"


# --- json_to_dataframes ---


def test_json_to_dataframes_returns_dict_of_dataframes():
    mapper = MapperConfig(columns=[ColumnConfig(header="A", path="a")])
    data = [{"a": 1}, {"a": 2}]
    dfs = json_to_dataframes(data, mapper)
    assert "Sheet1" in dfs
    assert isinstance(dfs["Sheet1"], pd.DataFrame)
    assert len(dfs["Sheet1"]) == 2


# --- excel_to_json (mocked) ---


def test_excel_to_json_with_mock_manager():
    mapper = MapperConfig(columns=[
        ColumnConfig(header="Property", path="$key"),
        ColumnConfig(header="Type", path="type"),
    ])
    mock_df = pd.DataFrame([{"Property": "bankName", "Type": "string"}])
    mock_manager = MagicMock()
    mock_manager.get_sheet_data.return_value = mock_df

    result = excel_to_json(
        "file.xlsx", "Sheet1", mapper,
        "user", "repo", "JIRA-1",
        excel_manager=mock_manager,
    )
    assert len(result) == 1
    assert result[0].get("$key") == "bankName" and result[0].get("type") == "string"


# --- json_to_excel (mocked) ---


def test_json_to_excel_with_mock_manager():
    mapper = MapperConfig(columns=[ColumnConfig(header="A", path="a")])
    data = [{"a": 1}]
    mock_manager = MagicMock()
    mock_manager.create_worksheet.return_value = True
    mock_manager.append_rows.return_value = True

    msg = json_to_excel(
        data, mapper, "out.xlsx", "Sheet1",
        "user", "repo", "JIRA-1",
        excel_manager=mock_manager,
    )
    assert "Wrote" in msg or "sheet" in msg.lower()
    assert mock_manager.append_rows.called


# --- sheet_data_to_json_shape ---


def test_sheet_data_to_json_shape_root_list():
    """No rowSourcePath: returns list of path-based row dicts (default sheet)."""
    mapper = MapperConfig(columns=[
        ColumnConfig(header="User ID", path="id"),
        ColumnConfig(header="Name", path="name"),
    ])
    sheet_data = {
        "Sheet1": [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ],
    }
    result = sheet_data_to_json_shape(sheet_data, mapper)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == {"id": "1", "name": "Alice"}
    assert result[1] == {"id": "2", "name": "Bob"}


def test_sheet_data_to_json_shape_root_list_uses_first_sheet_when_no_sheet1():
    mapper = MapperConfig(columns=[ColumnConfig(header="A", path="a")])
    sheet_data = {"Other": [{"a": 1}]}
    result = sheet_data_to_json_shape(sheet_data, mapper)
    assert result == [{"a": 1}]


def test_sheet_data_to_json_shape_row_source_path_single_sheet():
    """rowSourcePath, single sheet: returns dict with structure at rowSourcePath."""
    mapper = MapperConfig(
        rowSourcePath="components.schemas.PymtBankParam.properties",
        columns=[
            ColumnConfig(header="Property", path="$key"),
            ColumnConfig(header="Type", path="$key/type"),
            ColumnConfig(header="Description", path="$key/description"),
        ],
    )
    sheet_data = {
        "Sheet1": [
            {"$key": "bankName", "type": "string", "description": "Bank Name"},
            {"$key": "noOfPastDays", "type": "number", "description": "Past days"},
        ],
    }
    result = sheet_data_to_json_shape(sheet_data, mapper)
    assert isinstance(result, dict)
    assert result["components"]["schemas"]["PymtBankParam"]["properties"]["bankName"] == {
        "type": "string",
        "description": "Bank Name",
    }
    assert result["components"]["schemas"]["PymtBankParam"]["properties"]["noOfPastDays"] == {
        "type": "number",
        "description": "Past days",
    }


def test_sheet_data_to_json_shape_row_source_path_multi_sheet():
    """rowSourcePath, multiple sheets: main sheet fills rowSourcePath; ref sheet sets full paths."""
    mapper = MapperConfig(
        rowSourcePath="components.schemas.MyModel.properties",
        refMode="uniqueSheet",
        columns=[
            ColumnConfig(header="Property", path="$key"),
            ColumnConfig(header="Type", path="$key/type"),
            ColumnConfig(header="Description", path="$key/description"),
        ],
    )
    sheet_data = {
        "Sheet1": [
            {"$key": "id", "type": "string", "description": "Primary key"},
        ],
        "Address": [
            {"$key": "billingAddress.street", "type": "string", "description": "Street"},
            {"$key": "billingAddress.city", "type": "string", "description": "City"},
        ],
    }
    result = sheet_data_to_json_shape(sheet_data, mapper)
    assert isinstance(result, dict)
    assert result["components"]["schemas"]["MyModel"]["properties"]["id"] == {
        "type": "string",
        "description": "Primary key",
    }
    assert result["billingAddress"]["street"] == {"type": "string", "description": "Street"}
    assert result["billingAddress"]["city"] == {"type": "string", "description": "City"}


# --- merge_excel_into_json ---


def test_merge_excel_into_json_preserves_original():
    """Merge with sheet data that matches original: result equals original (round-trip)."""
    mapper = MapperConfig(columns=[
        ColumnConfig(header="User ID", path="id"),
        ColumnConfig(header="Name", path="name"),
    ])
    original = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    sheet_data = {
        "Sheet1": [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ],
    }
    result = merge_excel_into_json(original, sheet_data, mapper)
    assert result == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    assert original[0]["id"] == 1  # original unchanged (not in_place)


def test_merge_excel_into_json_overlay_wins():
    """Overlay (sheet) values overwrite original at same paths."""
    mapper = MapperConfig(columns=[
        ColumnConfig(header="A", path="a"),
        ColumnConfig(header="B", path="b"),
    ])
    original = [{"a": 1, "b": "old", "c": "keep"}]
    sheet_data = {"Sheet1": [{"a": 10, "b": "new"}]}
    result = merge_excel_into_json(original, sheet_data, mapper)
    assert result[0]["a"] == 10
    assert result[0]["b"] == "new"
    assert result[0]["c"] == "keep"


def test_merge_excel_into_json_list_by_index():
    """Lists merge by index; overlay element at i overwrites/merges with base[i]."""
    mapper = MapperConfig(columns=[
        ColumnConfig(header="X", path="x"),
    ])
    original = [{"x": 1, "y": 10}, {"x": 2, "y": 20}]
    sheet_data = {"Sheet1": [{"x": 100}, {"x": 200}]}
    result = merge_excel_into_json(original, sheet_data, mapper)
    assert result[0]["x"] == 100 and result[0]["y"] == 10
    assert result[1]["x"] == 200 and result[1]["y"] == 20


def test_merge_excel_into_json_in_place():
    """in_place=True mutates original."""
    mapper = MapperConfig(columns=[ColumnConfig(header="A", path="a")])
    original = [{"a": 1}]
    sheet_data = {"Sheet1": [{"a": 2}]}
    result = merge_excel_into_json(original, sheet_data, mapper, in_place=True)
    assert result is original
    assert original[0]["a"] == 2
