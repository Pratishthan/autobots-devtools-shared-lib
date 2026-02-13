# 13-Feb


2. Update stream_agent_events (Simplified, No Backward Compatibility)

 File: autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/ui/ui_utils.py

 Changes:

- Remove session_id parameter entirely
- Replace trace_metadata: dict | None with trace_metadata: TraceMetadata | None
- Remove metadata extraction logic (lines 148-155)
- Simplify tracing handler setup (lines 135-146)
- Auto-populate input_state["session_id"] from metadata if missing
- Use metadata.to_dict() instead of manual merge in span creation (line 174)

New signature:
` async def stream_agent_events(
     agent: Any,
     input_state: dict[str, Any],
     config: RunnableConfig,
     on_structured_output: Callable[[dict[str, Any], str | None], str] | None = None,
     enable_tracing: bool = True,
     trace_metadata: TraceMetadata | None = None,
 ) -> None:`


3. Apply Same Pattern to batch_invoker (Simplified)

 File: autobots-devtools-shared-lib/src/autobots_devtools_shared_lib/dynagent/agents/batch.py

 Changes:

- Remove batch_id parameter entirely
- Replace trace_metadata: dict | None with trace_metadata: TraceMetadata | None
- Remove metadata extraction logic (lines 180-185)
- Use metadata.to_dict() in span creation
- Use trace_metadata.session_id instead of batch_id

` New signature:
 def batch_invoker(
     agent_name: str,
     records: list[str],
     callbacks: list[Any] | None = None,
     enable_tracing: bool = True,
     trace_metadata: TraceMetadata | None = None,
 ) -> BatchResult:`
