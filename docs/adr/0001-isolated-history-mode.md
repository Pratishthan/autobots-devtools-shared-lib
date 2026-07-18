# Isolated history mode: payload-only spine, archives in graph state

Status: accepted

Domains can opt into `history_mode: isolated` (top-level `agents.yaml` key), replacing the shared
message list with per-agent contexts: on handoff the departing agent's live slice is archived under
its name and the arriving agent starts fresh with the in-flight user message plus a payload governed
by the departing agent's per-agent flag (`summary` — default — | `full` | `none`). Two decisions
here will surprise future readers:

## Arriving agents do not see the original user request (payload-only spine)

We considered always carrying the session's originating message(s) to every arriving agent, or
injecting a synthetic task brief from state fields. We chose purist isolation instead: durable task
facts (jira number, repo, file paths) must flow through the context store and prompt injection,
never through messages. Messages carry conversation; the spine carries facts. This keeps the
payload contract single-purpose (it describes the departing agent's *work*) and forces domains to
be explicit about what is durable. The one exception is deliberate: the in-flight user message of
the current turn always reaches the arriving agent regardless of flag, because it is the user's
live request, not the departing agent's work — without it, conversational handoffs with `none`
would be unanswerable.

## Archives and summaries live in graph state, not the Postgres/Redis context store

`agent_archives` and `agent_summaries` are Dynagent state keys written atomically by the handoff
`Command`, riding whatever checkpointer the domain configures (AMA already runs AsyncPostgresSaver).
The alternative — the existing context store — would decouple bulk from checkpoint state but makes
archive writes non-atomic with the agent transition and silently disables the feature in sessions
without the store configured. Consequence: `state["messages"]` is no longer the conversation; the
user-facing transcript must be reassembled (archived slices in visit order + current live slice)
via the engine helper, and anything reading raw `messages` for display must migrate to it.

## Consequences

- Summaries are the only cross-agent channel; explicit retrieval is own-archive-only. A
  reviewer-style agent cannot read an upstream agent's raw reasoning — accepted deliberately.
- Summaries are generated lazily (departure when flagged, else first revisit) and roll forward
  (prior summary + newest visit), so cost stays bounded per hop.
- The global `SummarizationMiddleware` remains as a safety net; if it compacts mid-visit, the
  archive captures the post-compaction slice — audit fidelity is bounded by compaction.
- Classic engine only; the deep engine isolates subagent contexts by construction.
