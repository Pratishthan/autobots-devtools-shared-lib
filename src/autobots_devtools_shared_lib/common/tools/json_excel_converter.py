# ABOUTME: Generic JSON ↔ Excel converter driven by mapper config.
# ABOUTME: Uses ExcelSheetsManager (xlsheets) / xlserver for Excel I/O.

from __future__ import annotations

import copy
import json
from typing import Any

from autobots_devtools_shared_lib.common.config.json_excel_mapper_config import (
    ColumnConfig,
    MapperConfig,
load_mapper_config,json
)
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)

# Default sheet name when no rowSourcePath or single sheet
_DEFAULT_SHEET = "Sheet1"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def get_value_by_path(obj: dict[str, Any], path: str) -> Any:
    """Get value at dot-path; if path starts with $key/, resolve remainder on same obj."""
    if not path or not path.strip():
        return None
    p = path.strip()
    if p.startswith("$key/"):
        p = p[5:].strip()
    if not p:
        return obj.get("$key")
    parts = p.split(".")
    current: Any = obj
    for part in parts:
        if current is None or not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def set_value_by_path(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set value at dot-path; create nested dicts as needed. $key/ prefix uses remainder."""
    if not path or not path.strip():
        return
    p = path.strip()
    if p.startswith("$key/"):
        p = p[5:].strip()
    if not p:
        obj["$key"] = value
        return
    parts = p.split(".")
    current = obj
    for i, part in enumerate(parts[:-1]):
        if part not in current or not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


# ---------------------------------------------------------------------------
# Ref resolution and row building
# ---------------------------------------------------------------------------


def _get_object_at_path(data: dict[str, Any], path_str: str) -> Any:
    """Traverse data by dot path. Returns None if path missing."""
    if not path_str or not path_str.strip():
        return data
    current: Any = data
    for part in path_str.strip().split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _resolve_ref(root: dict[str, Any], ref_value: str | dict[str, Any]) -> dict[str, Any] | None:
    """Resolve $ref against root. ref_value is '#/components/schemas/X' or {'$ref': '...'}."""
    ref_str = ref_value.get("$ref", ref_value) if isinstance(ref_value, dict) else ref_value
    if not isinstance(ref_str, str) or not ref_str.startswith("#/"):
        return None
    frag = ref_str[2:].strip("/")
    parts = frag.split("/")
    current: Any = root
    for part in parts:
        if current is None or not isinstance(current, dict):
            return None
        current = current.get(part)
    return current if isinstance(current, dict) else None


def _is_ref(v: Any) -> bool:
    return isinstance(v, dict) and "$ref" in v


def _is_array_type(v: Any) -> bool:
    return isinstance(v, dict) and v.get("type") == "array"


def _is_serial_column(col: ColumnConfig) -> bool:
    """True if column is generated serial number (type serial or gen-sl)."""
    return col.type in ("serial", "gen-sl")


def _cell_value(value: Any, col: ColumnConfig) -> str:
    """Format value for a cell: primitive array → join; non-primitive → json.dumps; else str."""
    if value is None:
        return ""
    if col.type == "array" and isinstance(value, list):
        if not value:
            return ""
        if col.elementType and all(type(x).__name__ in ("str", "int", "float", "bool") for x in value):
            return col.delimiter.join(str(x) for x in value)
        return json.dumps(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def _rows_from_row_source(
    data: dict[str, Any],
    mapper: MapperConfig,
) -> list[tuple[str, dict[str, Any]]]:
    """Produce (sheet_name, row) tuples from rowSourcePath + refMode."""
    path_str = mapper.rowSourcePath or ""
    obj = _get_object_at_path(data, path_str)
    if obj is None or not isinstance(obj, dict):
        return []

    ref_mode = mapper.refMode
    default_sheet = _DEFAULT_SHEET
    out: list[tuple[str, dict[str, Any]]] = []

    for k, v in obj.items():
        if ref_mode == "parentOnly":
            row = {"$key": k}
            if isinstance(v, dict) and not _is_ref(v) and not _is_array_type(v):
                row.update(v)
            else:
                row["_raw"] = v
            out.append((default_sheet, row))
            continue

        if _is_array_type(v):
            out.append((default_sheet, {"$key": k, **v}))
            continue

        if _is_ref(v):
            resolved = _resolve_ref(data, v)
            if not resolved or not isinstance(resolved, dict):
                out.append((default_sheet, {"$key": k, **v}))
                continue
            props = resolved.get("properties")
            if not isinstance(props, dict):
                out.append((default_sheet, {"$key": k, **resolved}))
                continue
            schema_name = str(resolved.get("title") or resolved.get("x-title") or "Schema")
            for ck, cv in props.items():
                child_row = {"$key": f"{k}.{ck}", **(cv if isinstance(cv, dict) else {"_value": cv})}
                if ref_mode == "inline":
                    out.append((default_sheet, child_row))
                elif ref_mode == "uniqueSheet":
                    out.append((schema_name, child_row))
                else:
                    out.append((k, child_row))
        else:
            row = {"$key": k, **(v if isinstance(v, dict) else {"_value": v})}
            out.append((default_sheet, row))

    return out


def _normalize_data(data: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """Ensure data is list of row dicts."""
    if isinstance(data, list):
        return data
    return [data]


def _resolve_mapper(mapper: MapperConfig | str, mapper_base_path: str | None, workspace_context: str, session_id: str | None) -> MapperConfig:
    if isinstance(mapper, MapperConfig):
        return mapper
    return load_mapper_config(mapper, mapper_base_path, workspace_context, session_id)


def _set_nested_path(obj: dict[str, Any], path_str: str, value: Any) -> None:
    """Set value at dot-path in obj, creating nested dicts. No $key/ handling."""
    if not path_str or not path_str.strip():
        return
    parts = path_str.strip().split(".")
    current = obj
    for i, part in enumerate(parts[:-1]):
        if part not in current or not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _deep_merge(base: Any, overlay: Any) -> Any:
    """Deep merge overlay into base. Overlay values take precedence.
    Two dicts: recurse.
    Two lists: if overlay is empty, return [] (overwrite/clear); else if both are list-of-dicts,
    merge by index; else overlay overwrites.
    Otherwise overlay wins.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = dict(base)
        for k, ov in overlay.items():
            if k in out:
                out[k] = _deep_merge(out[k], ov)
            else:
                out[k] = copy.deepcopy(ov)
        return out
    if isinstance(base, list) and isinstance(overlay, list):
        if not overlay:
            return copy.deepcopy(overlay)  # empty overlay clears the list (e.g. validValues removed in Excel)
        if all(isinstance(x, dict) for x in overlay) and all(isinstance(x, dict) for x in base):
            out = list(base)
            for i, ov in enumerate(overlay):
                if i < len(out):
                    out[i] = _deep_merge(out[i], ov)
                else:
                    out.append(copy.deepcopy(ov))
            return out
        return copy.deepcopy(overlay)  # value lists: overlay overwrites
    return copy.deepcopy(overlay)


def sheet_data_to_json_shape(
    sheet_data: dict[str, list[dict[str, Any]]],
    mapper: MapperConfig | str,
    mapper_base_path: str | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Convert path-based sheet_data back to JSON with the same shape as the mapper implies.
    No rowSourcePath: returns list of row dicts (default sheet).
    rowSourcePath: returns one dict with structure at rowSourcePath; multi-sheet merges ref paths.
    """
    cfg = _resolve_mapper(mapper, mapper_base_path, workspace_context, session_id)

    # Only return raw list of rows when there is no rowSourcePath at all (None)
    if cfg.rowSourcePath is None:
        rows = sheet_data.get(_DEFAULT_SHEET)
        if rows is None and sheet_data:
            rows = next(iter(sheet_data.values()), [])
        return list(rows) if rows else []

    path_str = (cfg.rowSourcePath or "").strip()
    root: dict[str, Any] = {}
    sheet_names = list(sheet_data.keys())
    main_sheet = _DEFAULT_SHEET if _DEFAULT_SHEET in sheet_data else (sheet_names[0] if sheet_names else None)
    ref_sheets = [s for s in sheet_names if s != main_sheet]

    if main_sheet is not None:
        props: dict[str, Any] = {}
        for row in sheet_data.get(main_sheet, []):
            key = row.get("$key")
            if key is None:
                continue
            # Build value from row without including $key (it's the property name, not part of the value)
            val = {}
            for k, v in row.items():
                if k == "$key":
                    continue
                if k.startswith("$key/"):
                    val[k[5:].strip()] = v
                else:
                    val[k] = v
            props[key] = val if val else row.get("_value") or {}
        if path_str:
            _set_nested_path(root, path_str, props)
        else:
            # Empty path = root object; result is the keyed object itself
            root.update(props)

    for sheet in ref_sheets:
        for row in sheet_data.get(sheet, []):
            key_path = row.get("$key")
            if not key_path:
                continue
            val = {}
            for k, v in row.items():
                if k == "$key":
                    continue
                if k.startswith("$key/"):
                    val[k[5:].strip()] = v
                else:
                    val[k] = v
            if val:
                set_value_by_path(root, key_path, val)
            else:
                for k, v in row.items():
                    if k != "$key" and v is not None:
                        set_value_by_path(root, key_path, v)
                        break

    return root


def merge_excel_into_json(
    original_json: list[dict[str, Any]] | dict[str, Any],
    sheet_data: dict[str, list[dict[str, Any]]],
    mapper: MapperConfig | str,
    mapper_base_path: str | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
    in_place: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Merge user-filled sheet_data (path-based) into original_json at mapper paths.
    Returns original + sheet values applied; if not in_place, returns a deep copy.
    """
    partial = sheet_data_to_json_shape(sheet_data, mapper, mapper_base_path, workspace_context, session_id)
    base = original_json if in_place else copy.deepcopy(original_json)
    return _deep_merge(base, partial)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def json_to_sheet_data(
    data: list[dict[str, Any]] | dict[str, Any],
    mapper: MapperConfig | str,
    mapper_base_path: str | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return sheet name → list of row dicts (header → cell value). No file I/O."""
    cfg = _resolve_mapper(mapper, mapper_base_path, workspace_context, session_id)

    if cfg.rowSourcePath is not None:
        pairs = _rows_from_row_source(data if isinstance(data, dict) else (data[0] if data and isinstance(data, list) else {}), cfg)
        by_sheet: dict[str, list[dict[str, Any]]] = {}
        for idx, (sheet_name, row) in enumerate(pairs):
            if sheet_name not in by_sheet:
                by_sheet[sheet_name] = []
            cell_row: dict[str, Any] = {}
            for col in cfg.columns:
                if _is_serial_column(col):
                    cell_row[col.header] = idx + 1
                else:
                    val = get_value_by_path(row, col.path)
                    cell_row[col.header] = _cell_value(val, col)
            by_sheet[sheet_name].append(cell_row)
        return by_sheet

    rows = _normalize_data(data)
    result: dict[str, list[dict[str, Any]]] = {_DEFAULT_SHEET: []}
    for idx, row in enumerate(rows):
        cell_row = {}
        for col in cfg.columns:
            if _is_serial_column(col):
                cell_row[col.header] = idx + 1
            else:
                val = get_value_by_path(row, col.path)
                cell_row[col.header] = _cell_value(val, col)
        result[_DEFAULT_SHEET].append(cell_row)
    return result


def json_to_dataframes(
    data: list[dict[str, Any]] | dict[str, Any],
    mapper: MapperConfig | str,
    mapper_base_path: str | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Return sheet name → pandas DataFrame. Requires pandas."""
    import pandas as pd

    sheet_data = json_to_sheet_data(data, mapper, mapper_base_path, workspace_context, session_id)
    return {name: pd.DataFrame(rows) for name, rows in sheet_data.items()}


def json_to_excel(
    data: list[dict[str, Any]] | dict[str, Any],
    mapper: MapperConfig | str,
    file_path: str,
    worksheet_name: str,
    user_name: str,
    repo_name: str,
    jira_number: str,
    mapper_base_path: str | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
    excel_manager: Any = None,
) -> str:
    """Write JSON data to Excel via ExcelSheetsManager. Returns success message."""
    import pandas as pd

    sheet_data = json_to_sheet_data(data, mapper, mapper_base_path, workspace_context, session_id)
    if excel_manager is None:
        try:
            from autobots_devtools_shared_lib.converter.xlsheets import ExcelSheetsManager

            excel_manager = ExcelSheetsManager()
        except Exception as e:
            logger.warning("ExcelSheetsManager not available: %s", e)
            return f"Error: ExcelSheetsManager not available — {e!s}"

    written: list[str] = []
    for sheet_name, rows in sheet_data.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        wname = sheet_name if len(sheet_data) > 1 or sheet_name != _DEFAULT_SHEET else worksheet_name
        try:
            excel_manager.create_worksheet(file_path, wname, user_name, repo_name, jira_number)
        except Exception:
            pass
        success = excel_manager.append_rows(file_path, wname, df, user_name, repo_name, jira_number)
        if success:
            written.append(wname)
    return f"Wrote sheets: {', '.join(written)}" if written else "No data written"


def excel_to_json(
    file_path: str,
    worksheet_name: str,
    mapper: MapperConfig | str,
    user_name: str,
    repo_name: str,
    jira_number: str,
    mapper_base_path: str | None = None,
    workspace_context: str = "{}",
    session_id: str | None = None,
    excel_manager: Any = None,
) -> list[dict[str, Any]]:
    """Read worksheet via ExcelSheetsManager and return list of row dicts (path → value)."""
    cfg = _resolve_mapper(mapper, mapper_base_path, workspace_context, session_id)
    if excel_manager is None:
        try:
            from autobots_devtools_shared_lib.converter.xlsheets import ExcelSheetsManager

            excel_manager = ExcelSheetsManager()
        except Exception as e:
            logger.warning("ExcelSheetsManager not available: %s", e)
            return []

    try:
        df = excel_manager.get_sheet_data(file_path, worksheet_name, user_name, repo_name, jira_number)
    except Exception as e:
        logger.warning("get_sheet_data failed: %s", e)
        return []

    if df is None or df.empty:
        return []
    headers = list(df.columns)
    out: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        row_dict: dict[str, Any] = {}
        for col in cfg.columns:
            if col.header not in headers or _is_serial_column(col):
                continue
            val = r.get(col.header)
            if col.type == "array":
                if val is None or (isinstance(val, str) and not val.strip()):
                    val = []
                elif isinstance(val, str) and col.delimiter:
                    val = [x.strip() for x in val.split(col.delimiter)]
                    if val == [""]:
                        val = []
            set_value_by_path(row_dict, col.path, val)
        out.append(row_dict)
    return out
