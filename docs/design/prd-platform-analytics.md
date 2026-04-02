# PRD: Platform Analytics & Usage Tracking

**Status:** DRAFT (interview in progress)
**Date:** 2026-03-25

---

## Problem Statement

As users adopt Designer and Nurture domains (and future domains), there is no way to track usage, collect feedback, or capture signals for improving code generation quality. Management needs reporting on adoption (who, what, when), and the engineering team needs a feedback loop from user edits to improve generators.

## Solution

A platform-level analytics system embedded in **autobots-devtools-shared-lib** (Dynagent framework) so any app built on Dynagent gets tracking for free. Data stored in Postgres (existing infra), consumed via Apache Superset or similar BI tool. Designed for eventual migration to ClickHouse.

## Constraints

- Version controlled in GitHub
- No additional infrastructure (reuse existing Postgres + Redis)
- Must be platform-level (shared-lib), not app-specific
- Schema must be framework-agnostic (not coupled to Chainlit or any specific UI)

## Scope: What's Tracked vs What's Not

### Tracked by this system (4 touch points)

1. **Chat message feedback** — User thumbs up/down + optional text + tags on assistant messages
2. **Workspace file scan** — Lines of code, file counts by folder (maps to generation mechanism: deterministic vs LLM)
3. **Code diff on PR approval** — GitHub Action compares generated snapshot (Git tag) against approved PR to capture user corrections
4. **Feature start event** — Triggered by `set_context` / create workspace; marks beginning of a feature

### NOT tracked by this system (covered elsewhere)

- Agent invocation traces (token usage, duration, success/fail) → **Langfuse**
- User session events (login, domain access, session duration) → **Langfuse**
- Pipeline stage completion → **Separate PRD** (assume available as dependency)

## Common Key

All analytics records share a composite key:

```
app_name + user_name + repo_name + jira_number
```

Example: `nurture + pralhad-2801541_infosys + fbp-core-collection + MER-12345`

## Touch Point Details

### 1. Chat Message Feedback

- **UI surface:** Chainlit's native feedback widget (thumbs up/down + free-text comment)
- **Integration:** Intercept Chainlit's feedback callback, write to **our own Postgres table** with controlled schema
- **Schema must be UI-agnostic** — if Chainlit is replaced, only the interceptor changes; the table stays the same
- **Extra feature:** Support category tags (e.g., "wrong code", "missing import", "good output")
- **Record includes:** composite key + message content/ID + rating + comment + tags + timestamp

### 2. Workspace File Scan

- **Approach:** Generic folder scanner — counts files and lines per folder. User knows which folder maps to which generation mechanism (deterministic vs LLM). No need to instrument each code gen path individually.
- **Trigger:** Automatic — either wired into orchestrator at stage boundaries, or triggered by the agent when it decides to checkpoint
- **Record includes:** composite key + folder path + file count + line count + language/extension + scan timestamp

### 3. Code Diff on PR Approval

- **Approach:** Git-native. Generated files are tagged/branched at generation time (snapshot). GitHub Action triggers on PR approval, diffs the generated tag against the approved version.
- **Purpose:** Captures user corrections as improvement signal for generators
- **Record includes:** composite key + files changed + lines added/removed + diff summary + PR URL + timestamp

### 4. Feature Start Event

- **Trigger:** `set_context` which triggers `create_workspace`
- **Purpose:** Marks the beginning of a feature; anchor point for all other events
- **Record includes:** composite key + task_name + timestamp

## Modules (Proposed)

1. **Analytics schema & repository** (shared-lib) — Postgres tables + DB layer for: feature_events, message_feedback, workspace_scans, code_diffs
2. **Feedback interceptor** (shared-lib) — Hooks into Chainlit's feedback callback, writes to controlled schema with composite key
3. **Workspace scanner** (shared-lib) — Generic folder scanner (files, lines, by extension), callable from orchestrators or agents
4. **Feature event tracker** (shared-lib) — Captures "feature started" event on set_context
5. **GitHub Action** (new workflow) — Triggers on PR approval, diffs generated tag against approved code, posts results to Postgres
6. **Orchestrator integration** (MER) — Wire workspace scans into orchestrator stage boundaries

## Open Items (to resolve when resuming)

- [ ] Module breakdown validation with user
- [ ] Which modules need tests
- [ ] Feedback tag categories — predefined list or free-form?
- [ ] Git tagging convention for generated snapshots
- [ ] GitHub Action: how does it connect to Postgres? (API endpoint? Direct DB?)
- [ ] Workspace scanner: should it run via file server sidecar or direct filesystem?
- [ ] User stories (full list)
- [ ] Testing decisions
- [ ] Out of scope section

## Out of Scope

TBD

## Further Notes

- Schema should use event-style rows with timestamps (ClickHouse-friendly for future migration)
- Reporting handled externally via Apache Superset — no dashboards built into the app
