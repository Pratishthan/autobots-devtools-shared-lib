# JSON ↔ Excel Bidirectional Converter — Usage Guide

This guide describes how to use the generic JSON ↔ Excel converter: mapper configuration, available methods, environment and dependencies, and typical workflows.

---

## 1. Overview

The converter turns JSON data into Excel sheet(s) and vice versa using a **mapper** (JSON config) that defines:

- **Columns**: Excel header name and the path into the JSON row (or object) for each field.
- **Row source** (optional): When set, rows are derived from an object at a given path (e.g. schema properties) instead of a root list.
- **Ref and array handling** (optional): How to expand `$ref` and non-primitive arrays (inline, one sheet per ref, etc.).
- **Serial column** (optional): A generated 1-based row number column in Excel, ignored on Excel → JSON.

**Sheet names:** The initial (main) sheet name can be set via the **model_name** parameter (e.g. the JSON file name). When not set, it defaults to `"Sheet1"`. Ref sheets use child model names: **uniqueSheet** uses the referenced schema’s title (e.g. "Address"); **perOccurrenceSheet** uses `{SchemaTitle}_{parentKey}` (e.g. "Address_billingAddress") so each occurrence has its own sheet named by the child model.

All Excel read/write goes through **ExcelSheetsManager** and **xlserver** (no direct openpyxl in the library). You can still work with in-memory sheet data (dict of rows) or DataFrames without hitting the server.

---

## 2. Mapper configuration

Mappers are JSON files. Each mapper has a **name** (filename without `.json`). You load by name from a configurable directory or via the file server.

### 2.1 Mapper structure

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| **columns** | array | Yes | — | List of column definitions (see below). |
| **rowSourcePath** | string | No | — | When set, rows come from the object at this dot-path (e.g. `components.schemas.X.properties`). Use `""` for root object keys. |
| **refMode** | string | No | `"inline"` | How to handle `$ref` and non-primitive arrays when using rowSourcePath: `inline`, `uniqueSheet`, `perOccurrenceSheet`, `parentOnly`. |

### 2.2 Column definition

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| **header** | string | Yes | — | Excel column header. |
| **path** | string | Yes | — | Dot-path into the row (e.g. `id`, `name.firstName`, `$key`, `$key/type`). Ignored when `type` is `serial` or `gen-sl`. |
| **type** | string | No | — | `array`: value is an array (primitive → join with delimiter; non-primitive → one cell). `serial` or `gen-sl`: generated row number; ignored on Excel → JSON. |
| **elementType** | string | No | — | Hint for array: `string`, `number`, `boolean`. |
| **delimiter** | string | No | `","` | Used when `type` is `array` for joining/splitting. |

### 2.3 Path semantics

- **Dot paths**: `id`, `name.firstName`, `values.validValues` read or write nested fields.
- **$key**: When using **rowSourcePath**, each row has an implicit key (e.g. property name). Use path `$key` to put that key in the column.
- **$key/…**: Fields on the same row’s value. For example, with rowSourcePath `components.schemas.PymtBankParam.properties`, each row is a property; `$key/type` and `$key/description` are the `type` and `description` of that property. So `$key/type` means “from the current row value, get `type`”.

### 2.4 refMode (when rowSourcePath is set)

| refMode | Flat $ref | Sheet names |
|---------|-----------|-------------|
| **inline** | Same sheet; $key = `parent.childKey` | Main sheet only (or model name when provided). |
| **uniqueSheet** | One sheet per unique ref schema; $key = `parent.childKey`. | Main sheet + one sheet per **child schema** (schema `title` or `x-title`, e.g. "Address"). |
| **perOccurrenceSheet** | One sheet per ref occurrence; $key = childKey only. | Main sheet + **{SchemaTitle}_{parentKey}** (e.g. `Address_billingAddress`, `Address_shippingAddress`). |
| **parentOnly** | One row per parent; ref in one cell (no expansion). | Main sheet only. |

Non-primitive arrays follow the same rules (inline = same sheet; uniqueSheet/perOccurrenceSheet = sheets by schema or occurrence).

### 2.5 Serial column

To add a 1-based row number column (e.g. “S.No”, “Serial No”):

- Add a column with **type** `serial` or `gen-sl` and any **header**. **path** can be `""` or any placeholder.
- **JSON → Excel**: That column is filled with 1, 2, 3, … . Place it first in `columns` to have it at the start of the sheet.
- **Excel → JSON**: This column is not mapped; it is ignored.

Example:

```json
{ "header": "S.No", "path": "", "type": "serial" }
```

### 2.6 Example mappers

**List of objects (root list):**

```json
{
  "columns": [
    { "header": "User ID", "path": "id" },
    { "header": "Phones", "path": "phones", "type": "array", "elementType": "string", "delimiter": "," },
    { "header": "First Name", "path": "name.firstName" },
    { "header": "Last Name", "path": "name.lastName" }
  ]
}
```

**One row per root key (rowSourcePath empty string):**

```json
{
  "rowSourcePath": "",
  "columns": [
    { "header": "S.No", "path": "", "type": "serial" },
    { "header": "Param Name", "path": "$key" },
    { "header": "Valid values", "path": "$key/values.validValues", "type": "array", "elementType": "string", "delimiter": "," },
    { "header": "Invalid values", "path": "$key/values.invalidValues", "type": "array", "elementType": "string", "delimiter": "," }
  ]
}
```

**One row per schema property (rowSourcePath to properties):**

```json
{
  "rowSourcePath": "components.schemas.PymtBankParam.properties",
  "columns": [
    { "header": "Property", "path": "$key" },
    { "header": "Type", "path": "$key/type" },
    { "header": "Description", "path": "$key/description" }
  ]
}
```

---

## 3. Environment and configuration

### 3.1 Mapper location

- **JSON_EXCEL_MAPPER_PATH** (optional): Directory where mapper `.json` files live. Used when you load a mapper **by name** and do **not** pass `mapper_base_path`.
- If you always pass `mapper_base_path` (or a `MapperConfig` object), you do not need this env var.

### 3.2 Loading mapper from file server

When you call `load_mapper_config(mapper_name, ..., workspace_context='{"workspace_base_path": "..."}', session_id=...)` with a non-empty `workspace_context`, the mapper file is read via the file server (`read_file`). No env var is required for that beyond your file server configuration (e.g. `FILE_SERVER_HOST`, `FILE_SERVER_PORT` if you use the file server client).

### 3.3 Excel read/write (xlserver)

- **json_to_excel** and **excel_to_json** use **ExcelSheetsManager**, which talks to **xlserver**.
- xlserver is configured with:
  - **EXCEL_SERVER_HOST** (default `0.0.0.0`)
  - **EXCEL_SERVER_PORT** (default `9001`)
  - **FILE_SERVER_URL** (file storage used by the Excel server)
  - **ENABLE_CORS**, **CORS_ORIGINS** as needed
- If the Excel server is not running or not reachable, `json_to_excel` returns an error message and `excel_to_json` returns `[]`. You can pass a mock or custom `excel_manager` for tests.

### 3.4 Dependencies

- **pandas**: Used by `json_to_dataframes` and by the converter when calling ExcelSheetsManager (DataFrames for append_rows / get_sheet_data). Declared in the package.
- **openpyxl**: Not required by the library; the **demo** uses it to write/read local `.xlsx` files for testing.

---

## 4. Public API

All of the following are in `autobots_devtools_shared_lib.common.tools`; mapper types and loader are in `autobots_devtools_shared_lib.common.config`.

### 4.1 load_mapper_config

Load a mapper by name (from disk or file server).

```python
from autobots_devtools_shared_lib.common.config import load_mapper_config

config = load_mapper_config(
    "test_params",
    mapper_base_path="/path/to/mappers",
    workspace_context="{}",
    session_id=None,
)
# config is a MapperConfig (columns, rowSourcePath, refMode)
```

- **mapper_name**: Mapper name; file is `{mapper_name}.json`.
- **mapper_base_path**: Directory of mapper files. If `None`, uses env **JSON_EXCEL_MAPPER_PATH** (must be set in that case).
- **workspace_context**: JSON string (e.g. `'{"workspace_base_path": "..."}'`). If non-empty, load via file server.
- **session_id**: Optional, for file server.

Raises `ValueError` if both `mapper_base_path` and `JSON_EXCEL_MAPPER_PATH` are missing. Raises `FileNotFoundError` if the mapper file is not found.

---

### 4.2 json_to_sheet_data

Convert JSON to in-memory sheet data (no Excel I/O). Use this when you want dict-of-rows only or when you write Excel yourself.

```python
from autobots_devtools_shared_lib.common.tools import json_to_sheet_data

data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
sheet_data = json_to_sheet_data(
    data,
    "list_objects",
    mapper_base_path="/path/to/mappers",
    model_name="users",
)
# sheet_data: dict[str, list[dict]] — sheet name → list of row dicts (header → cell value)
# e.g. {"users": [{"User ID": "1", "Name": "Alice"}, ...]} when model_name="users"
```

- **data**: List of objects or single object. With **rowSourcePath**, a dict is used (e.g. object at that path or root).
- **mapper**: Mapper name (string) or **MapperConfig** instance.
- **mapper_base_path**, **workspace_context**, **session_id**: Used when mapper is a string (see load_mapper_config).
- **model_name**: Optional. When set (e.g. JSON file name), used as the main sheet name instead of `"Sheet1"`.

Returns: `dict[str, list[dict]]` — sheet name → list of rows; each row is header → cell value. Serial columns get 1-based integers.

---

### 4.3 json_to_dataframes

Same as `json_to_sheet_data` but returns a **list of (sheet name, pandas DataFrame)** so each item has both name and rows. Requires pandas.

```python
from autobots_devtools_shared_lib.common.tools import json_to_dataframes

sheet_results = json_to_dataframes(
    data, "list_objects", mapper_base_path="/path/to/mappers", model_name="users"
)
# sheet_results: list[tuple[str, pd.DataFrame]] — e.g. [("users", df)]
for sheet_name, df in sheet_results:
    print(sheet_name, df.shape)
```

Parameters are the same as `json_to_sheet_data` (including **model_name**). Returns: `list[tuple[str, pd.DataFrame]]`.

---

### 4.4 json_to_excel

Convert JSON to Excel by writing through ExcelSheetsManager (xlserver). Use when you have a running Excel server.

```python
from autobots_devtools_shared_lib.common.tools import json_to_excel

msg = json_to_excel(
    data,
    "list_objects",
    file_path="Report.xlsx",
    worksheet_name="Sheet1",
    user_name="john",
    repo_name="my-repo",
    jira_number="JIRA-123",
    mapper_base_path="/path/to/mappers",
    excel_manager=None,
)
# msg: "Wrote sheets: Sheet1" or an error string
```

- **data**, **mapper**, **mapper_base_path**, **workspace_context**, **session_id**: Same as above.
- **file_path**: Target file/spreadsheet identifier for the Excel server.
- **worksheet_name**: Default worksheet name when there is only one sheet and **model_name** is not set.
- **user_name**, **repo_name**, **jira_number**: Passed to xlserver/ExcelSheetsManager.
- **excel_manager**: Optional; if provided, used instead of creating a default ExcelSheetsManager (useful for tests with a mock).
- **model_name**: Optional. When set (e.g. JSON file name), used as the main sheet name in the workbook.

Returns a success message string or an error description.

---

### 4.5 excel_to_json

Read one worksheet from Excel via ExcelSheetsManager and convert it to a list of path-based row dicts.

```python
from autobots_devtools_shared_lib.common.tools import excel_to_json

rows = excel_to_json(
    file_path="Report.xlsx",
    worksheet_name="Sheet1",
    mapper="list_objects",
    user_name="john",
    repo_name="my-repo",
    jira_number="JIRA-123",
    mapper_base_path="/path/to/mappers",
    excel_manager=None,
)
# rows: list[dict] — each dict has path → value (e.g. {"id": "1", "name": "Alice"})
```

- **file_path**, **worksheet_name**: Which file and sheet to read.
- **mapper**: Mapper name or MapperConfig.
- **user_name**, **repo_name**, **jira_number**: Passed to the Excel server.
- **excel_manager**: Optional; if provided, used for the read.

Returns `list[dict]` (path-based row objects). Columns with type `serial` or `gen-sl` are ignored. Empty cells for array columns become `[]`.

---

### 4.6 sheet_data_to_json_shape

Convert path-based sheet data (e.g. from Excel) back into the **shape** implied by the mapper: list of rows when there is no rowSourcePath, or a single dict when there is rowSourcePath (including multi-sheet refs). Use when you only have partial data in the sheet and want the same structure as the original JSON.

```python
from autobots_devtools_shared_lib.common.tools import sheet_data_to_json_shape

# sheet_data: dict[str, list[dict]] — path-based rows per sheet (e.g. from excel_to_json per sheet)
shape = sheet_data_to_json_shape(
    sheet_data,
    "test_params",
    mapper_base_path="/path/to/mappers",
)
# shape: list[dict] or dict — same shape as original (e.g. { "bankName": { "values": {...} }, ... })
```

- **sheet_data**: `dict[str, list[dict]]` where each row dict uses **paths** as keys (e.g. `$key`, `values`, `$key/type`), not header names.
- **mapper**: Mapper name or MapperConfig.
- **mapper_base_path**, **workspace_context**, **session_id**: Used when mapper is a string.

Returns: `list[dict]` when the mapper has no rowSourcePath; otherwise a single `dict` with the structure at rowSourcePath (and ref sheets merged). `$key` is not included inside value objects.

---

### 4.7 merge_excel_into_json

Merge user-filled sheet data into an existing JSON so that only the fields present in the sheet are updated; everything else stays from the original. Typical for “edit in Excel then write back”.

```python
from autobots_devtools_shared_lib.common.tools import merge_excel_into_json

original = {"bankName": {"values": {"validValues": ["A", "B"], "invalidValues": []}, "assertion": {...}}}
# sheet_data: path-based, e.g. from reading Excel with the same mapper
merged = merge_excel_into_json(
    original,
    sheet_data,
    "test_params",
    mapper_base_path="/path/to/mappers",
    in_place=False,
)
# merged: same type as original; sheet values overwrite at mapper paths. Empty list in sheet clears that list.
```

- **original_json**: Full JSON (list or dict) that was used to generate the sheet (or the stored document).
- **sheet_data**: Same format as for `sheet_data_to_json_shape` — path-based rows per sheet.
- **mapper**: Mapper name or MapperConfig.
- **in_place**: If `False` (default), merge into a copy; if `True`, merge into `original_json` in place.

Returns the same type as `original_json`. List fields in the sheet overwrite the original list (e.g. empty `validValues` in the sheet becomes `[]` in the result). Dicts are merged recursively.

---

## 5. Typical workflows

### 5.1 JSON → Excel (write)

1. Have a mapper and JSON data.
2. Option A: `json_to_sheet_data(data, mapper, ...)` then write the dict to Excel yourself (e.g. openpyxl in a script).
3. Option B: `json_to_dataframes(data, mapper, ...)` then use the DataFrames as you like.
4. Option C: `json_to_excel(data, mapper, file_path, worksheet_name, user_name, repo_name, jira_number, ...)` to write via xlserver.

### 5.2 Excel → JSON (read)

1. Read worksheet via ExcelSheetsManager (or your own reader that produces the same row structure).
2. Call `excel_to_json(file_path, worksheet_name, mapper, user_name, repo_name, jira_number, ...)` to get `list[dict]` (path-based rows). For multi-sheet work, read each sheet and build `sheet_data: dict[str, list[dict]]` yourself, or use the demo helper.

### 5.3 Partial Excel → JSON with original shape

1. Get path-based `sheet_data` from Excel (e.g. one sheet or multiple).
2. Call `sheet_data_to_json_shape(sheet_data, mapper, ...)` to get JSON in the same shape as the mapper (list or keyed object). Data may be partial; no `$key` inside value objects.

### 5.4 Merge user edits back into original JSON

1. Have **original** JSON and **sheet_data** (path-based) from the user-filled Excel.
2. Call `merge_excel_into_json(original, sheet_data, mapper, ...)` to get original with sheet values applied. Empty lists in the sheet overwrite and clear those fields in the result.

---

## 6. Demo

The **demo** in `demo/` shows all flows with sample mappers and data:

- **Run all scenarios**: `python demo/run_demo.py`
- **Single scenario**: `python demo/run_demo.py --json Test-Params.json --mapper test_params`
- **Excel → JSON only** (using an existing Excel in `demo/output/excel/`):
  `python demo/run_demo.py --excel list_objects.xlsx --mapper list_objects --json users.json`

See `demo/README.md` for layout, scenarios, and output files (sheet_data JSON, from_excel, shape, merged).

---

## 7. Summary

| Need | Method | Notes |
|------|--------|--------|
| Load mapper by name | `load_mapper_config` | Set `JSON_EXCEL_MAPPER_PATH` or pass `mapper_base_path`. |
| JSON → sheet data (no file) | `json_to_sheet_data` | Returns dict of rows; optional **model_name** for main sheet name; serial columns get 1, 2, 3, … . |
| JSON → DataFrames | `json_to_dataframes` | Returns **list of (name, DataFrame)**; optional **model_name**. Requires pandas. |
| JSON → Excel file (server) | `json_to_excel` | Needs xlserver; pass file_path, worksheet_name, user_name, repo_name, jira_number; optional **model_name**. |
| Excel → list of rows | `excel_to_json` | One worksheet; returns path-based rows; serial columns ignored. |
| Sheet data → JSON shape | `sheet_data_to_json_shape` | Path-based sheet_data → list or dict; no `$key` in values. |
| Merge sheet into original | `merge_excel_into_json` | Original + sheet_data → updated JSON; overlay overwrites (empty list clears). |

| Env / config | Purpose |
|--------------|--------|
| **JSON_EXCEL_MAPPER_PATH** | Default directory for mapper files when loading by name without `mapper_base_path`. |
| **EXCEL_SERVER_HOST** / **EXCEL_SERVER_PORT** | xlserver (used by json_to_excel / excel_to_json when using default ExcelSheetsManager). |
| **FILE_SERVER_URL** | Used by xlserver for file storage. |
| **workspace_context** | Non-empty to load mapper via file server instead of local path. |
