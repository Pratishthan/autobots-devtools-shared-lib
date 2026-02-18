# W3C Traceparent Propagation: Fileserver ↔ Dynagent

## Context

When `node_kb_builder.py` invokes the `schema_processor` agent, which calls the `write_file` tool (HTTP POST to `/writeFile`), the fileserver creates an **independent top-level trace** in Langfuse instead of appearing under the same session. This is because:

1. The HTTP client (`fserver_client_utils.py`) uses plain `httpx.Client()` with no trace context headers
2. The fileserver's OTEL instrumentation creates a new root trace for each request
3. No `session_id` flows from the agent context to the fileserver's OTEL span

**Goal:** Link the fileserver OTEL traces to the agent's Langfuse session via W3C `traceparent` header propagation + Langfuse `session_id` attribute.

## Approach

Create an OTEL client span in the HTTP client layer, inject W3C `traceparent` headers, and set `langfuse.session.id` on both client and server spans. The agent-side Langfuse native trace and the OTEL trace will appear as **separate traces under the same Langfuse session**.

All changes are in `autobots-devtools-shared-lib`.

---

## Changes

### 1. New file: `common/observability/trace_propagation.py`

**Path:** `src/autobots_devtools_shared_lib/common/observability/trace_propagation.py`

A helper module providing a `traced_http_call` context manager that:
- Lazily initializes an OTEL `TracerProvider` (only if no real provider already exists) exporting to Langfuse via OTLP (reuses existing `LANGFUSE_*` env vars)
- Creates a `SpanKind.CLIENT` span per HTTP call
- Sets `langfuse.session.id` and `langfuse.user.id` as span attributes
- Injects W3C `traceparent` header via `TraceContextTextMapPropagator.inject()`
- Yields a `dict[str, str]` of headers to pass to httpx
- Gracefully degrades (yields empty headers) if OTEL packages are not installed

Key design decisions:
- **Lazy init**: OTEL tracer created on first use only. If OTEL packages aren't installed, yields empty headers (no-op).
- **Provider guard**: Checks `type(current_provider).__name__ == "ProxyTracerProvider"` before creating a new one — avoids conflict if fileserver runs in the same process.
- **Reuses Langfuse OTLP config**: Same `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_BASE_URL` env vars.
- **`SpanKind.CLIENT`**: Pairs naturally with the server's `SpanKind.SERVER` span from `FastAPIInstrumentor`.

### 2. Update `common/utils/fserver_client_utils.py`

**Path:** `src/autobots_devtools_shared_lib/common/utils/fserver_client_utils.py`

For all 6 HTTP functions (`list_files`, `get_disk_usage`, `read_file`, `write_file`, `move_file`, `create_download_link`):
- Add optional `session_id: str | None = None` parameter
- Wrap the `httpx.Client()` call with `traced_http_call(operation, session_id=session_id)`
- Pass the yielded trace headers to `client.post()/get(..., headers=trace_headers)`
- For functions with a body payload, set `session_id` from `session_id` if not already present (reuses existing `session_id` field on the Pydantic models — no model changes needed)

Example pattern:
```python
def write_file(file_name: str, content: str, workspace_context: str = "{}", session_id: str | None = None) -> str:
    # ... existing payload construction ...
    if session_id:
        payload.setdefault("session_id", session_id)

    with traced_http_call("writeFile", session_id=session_id) as trace_headers:
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=trace_headers, timeout=30.0)
    # ... rest unchanged ...
```

### 3. Update `common/tools/fserver_client_tools.py`

**Path:** `src/autobots_devtools_shared_lib/common/tools/fserver_client_tools.py`

- Add `_session_id_from_runtime()` helper that extracts `session_id` from `runtime.state`
- Update all tool functions (`write_file_tool`, `read_file_tool`, `list_files_tool`, `move_file_tool`, `create_download_link_tool`) to pass `session_id=_session_id_from_runtime(runtime)` to the underlying client util functions

```python
def _session_id_from_runtime(runtime: ToolRuntime[None, Dynagent] | None) -> str | None:
    if runtime is None:
        return None
    state = runtime.state
    return state.get("session_id") if state is not None else None
```

### 4. Update `common/observability/otel_fastapi.py`

**Path:** `src/autobots_devtools_shared_lib/common/observability/otel_fastapi.py`

Two changes in `instrument_fastapi()`:
- **Explicit W3C propagator:** Add `set_global_textmap(TraceContextTextMapPropagator())` after the `TracerProvider` setup (ensures incoming `traceparent` headers are extracted)

One change in `_set_span_attributes()`:
- **Session linking:** After parsing the request body, extract `session_id` and set `langfuse.session.id` on the current span so the server trace appears in the correct Langfuse session

```python
# In _set_span_attributes(), after building input_data:
if request_body_parts:
    try:
        req_json = json.loads(b"".join(request_body_parts).decode("utf-8"))
        sid = req_json.get("session_id")
        if sid:
            span.set_attribute("langfuse.session.id", str(sid))
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
```

---

## Trace Flow After Implementation

```
Agent invocation (Langfuse native, session_id="abc123")
  └─ schema_processor agent executes write_file tool
       └─ fserver_client_utils.write_file(session_id="abc123")
            └─ traced_http_call("writeFile", session_id="abc123")
                 ├─ Creates OTEL CLIENT span (langfuse.session.id="abc123")
                 ├─ Injects traceparent: 00-{trace_id}-{span_id}-01
                 └─ HTTP POST /writeFile (session_id="abc123")
                      └─ FastAPI extracts traceparent → creates child SERVER span
                         └─ ASGI middleware sets langfuse.session.id="abc123"
```

**Result in Langfuse:** Both traces grouped under session `"abc123"`. The OTEL trace has proper client→server parent-child span hierarchy.

---

## No New Dependencies

All required packages are already in `pyproject.toml`:
- `opentelemetry-api>=1.30.0`
- `opentelemetry-sdk>=1.30.0`
- `opentelemetry-exporter-otlp-proto-http>=1.30.0`

---

## Verification

1. **Run existing tests:** `make test-fast` from `autobots-devtools-shared-lib/`
2. **Run type check:** `make type-check` from `autobots-devtools-shared-lib/`
3. **End-to-end test:** Run `node_kb_builder.py` → verify in Langfuse that:
   - The `kbe-pay-schema_processor` trace and `POST /writeFile` trace share the same session ID
   - The `/writeFile` OTEL trace shows a `traceparent`-linked client→server span hierarchy
   - Langfuse session view groups both traces together
