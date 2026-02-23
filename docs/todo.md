# Dynagent Shared Lib — Extension TODO

## Extension Areas

| # | Extension | What it solves | Proposed module |
|---|---|---|---|
| 1 | **Guardrails** | PII leakage, injection, content safety | `dynagent.guardrails` |
| 2 | **Tool RBAC** | Unauthorized tool access across agents | `dynagent.auth` |
| 3 | **Retry / Circuit Breaker** | External API resilience | `dynagent.resilience` |
| 4 | **Conversation Memory** | Context window bloat on long sessions | `dynagent.memory` |
| 5 | **Agent Metrics** | Operational visibility beyond traces | `dynagent.metrics` |
| 6 | **Event Bus / Webhooks** | External system integration | `dynagent.events` |

---

## 1. Guardrails (`dynagent.guardrails`)

- [ ] PII detection & masking (SSN, credit card, email in agent output)
- [ ] Content safety check (injection patterns: `eval`, `exec`, `<script>`, SQL)
- [ ] `GuardrailPipeline` — chainable pre/post processing hooks
- [ ] Guarded tool wrapper decorator for input validation + output sanitization
- [ ] Configurable per-domain guardrail profiles via `agents.yaml`

## 2. Tool Authorization / RBAC (`dynagent.auth`)

- [ ] `Role` enum (viewer, agent, admin, batch_processor)
- [ ] `ToolPermission` dataclass — allowed roles, allowed agents, rate limit
- [ ] `ToolAuthorizer` — enforce per-tool access control at invocation time
- [ ] Per-tool rate limiting (sliding window per user)
- [ ] Integration with `tool_registry.register()` for declarative permissions
- [ ] YAML-driven permission config alongside `agents.yaml`

## 3. Retry / Circuit Breaker (`dynagent.resilience`)

- [ ] `CircuitBreaker` — per-tool circuit with CLOSED → OPEN → HALF_OPEN states
- [ ] `@with_retry` decorator — exponential backoff + optional circuit breaker
- [ ] Async and sync support
- [ ] Configurable failure threshold, recovery timeout, max retries
- [ ] Integration with `AgentMetrics` for failure tracking

## 4. Conversation Memory (`dynagent.memory`)

- [ ] `ConversationTurn` dataclass with token estimation
- [ ] `ConversationMemory` — rolling history with automatic summarization
- [ ] Compaction: summarize older turns, keep recent N verbatim
- [ ] `get_context_for_agent()` — build context window post-handoff
- [ ] Integration with `context_store` for persistence across sessions
- [ ] Token budget enforcement to prevent context window overflow

## 5. Agent Metrics (`dynagent.metrics`)

- [ ] `ToolMetric` — call count, error count, latency tracking
- [ ] `AgentMetrics` singleton — tool calls, handoff counts, agent invocations
- [ ] `track_tool()` context manager for automatic timing
- [ ] `snapshot()` export for `/healthz` endpoint or Prometheus/Datadog
- [ ] Error rate and avg latency computation per tool
- [ ] Handoff frequency tracking (source → target agent pairs)

## 6. Event Bus / Webhooks (`dynagent.events`)

- [ ] `EventType` enum (ticket.created, lead.qualified, agent.handoff, agent.error, session.*)
- [ ] `AgentEvent` dataclass with typed payload
- [ ] `EventBus` — async pub/sub with error-resilient dispatch
- [ ] Subscriber registration per event type
- [ ] Example subscribers: Slack notification, CRM webhook
- [ ] `emit()` helpers for common events from within tools

---

## Lighter-Weight Extensions (Future)

- [ ] **Tool Result Caching** — LRU/TTL cache for idempotent tools (e.g., KB search)
- [ ] **Agent Config Validation** — Pydantic model for `agents.yaml` with startup-time errors
- [ ] **Prompt Versioning** — Hash-based prompt diffing tied to Langfuse generations for A/B testing
