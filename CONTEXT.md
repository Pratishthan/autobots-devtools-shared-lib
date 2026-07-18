# Dynagent

Multi-agent framework where YAML-configured agents on a single LangGraph share a session and pass control via handoff.

## Language

### Agents & control flow

**Handoff**:
The act of transferring control from one agent to the next within a session.
_Avoid_: transfer, delegation, routing

**Visit**:
One contiguous span during which an agent holds control, from its arrival (session start or inbound handoff) to its departure (outbound handoff). An agent may have many visits per session.
_Avoid_: turn, episode

### Message history

**History Mode**:
A domain-level property declaring how agents see conversation history: `shared` (all agents read one common message list) or `isolated` (each agent works in its own context).
_Avoid_: memory mode, context mode

**Live Slice**:
The messages currently in an agent's working context during its visit. In isolated mode this is all the LLM sees, besides what its prompt injects.
_Avoid_: active history, working memory

**Archive**:
An agent's append-only record of its past visits' live slices, kept in visit order. Private to that agent; other agents never read it raw.
_Avoid_: history log, backlog

**Agent Summary**:
The rolling condensation of an agent's archive: each update folds the newest visit into the prior summary. Generated lazily — only when a handoff needs it.
_Avoid_: memo, recap

**Handoff Payload**:
What the arriving agent receives about the departing agent's work, governed by the departing agent's Payload Flag.
_Avoid_: handoff context, briefing

**Payload Flag**:
A per-agent declaration of what its departure hands over: `summary` (its Agent Summary), `full` (its live slice verbatim), or `none` (nothing about its work).
_Avoid_: share mode

**In-flight User Message**:
The user message of the turn being processed when a handoff fires. It always reaches the arriving agent, regardless of Payload Flag — it is the user's live request, not the departing agent's work.
_Avoid_: pending message, current query

**Context Spine**:
The durable task facts of a session (identifiers, paths, parameters) carried by the context store and prompt injection — never by messages. In isolated mode, messages carry conversation; the spine carries facts.
_Avoid_: session context (ambiguous with the context store itself)

**Transcript**:
The user-facing conversation of a session, reassembled chronologically from all agents' archives plus the current live slice. Distinct from any single agent's context.
_Avoid_: chat history, message history (ambiguous)
