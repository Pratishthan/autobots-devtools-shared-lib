# Prompt Evaluation Architecture — Dynagent Framework

**Status:** Architectural Plan — Ready for Review
**Tech Stack:** Python 3.12+, LangChain, LangGraph, Langfuse, YAML, GitHub Actions
**Scope:** Langfuse-native eval pipeline with multi-turn datasets per sub-agent

---

## 1. Problem Statement

Prompts live in GitHub as markdown files alongside code — good for version control, bad for evaluation. Today the feedback loop is:

```
change prompt → deploy → observe in production (Langfuse traces) → react
```

The gap: **no way to know if a prompt change improved agent behavior before merge.** Prompt quality is empirical — a diff shows *what* changed, not *whether it's better*.

### Sub-Problems

| # | Problem | Current State | Target State |
|---|---------|--------------|--------------|
| A | Prompt source of truth | GitHub markdown files | No change — GitHub stays |
| B | Pre-merge evaluation | Manual testing / vibes | Automated eval in CI, scored in Langfuse |
| C | Production → eval loop | Langfuse traces observed manually | Traces mined into eval datasets via PRs |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        GitHub Repo                          │
│                                                             │
│  domains/customer-support/                                  │
│    prompts/                                                 │
│      01-coordinator.md                                      │
│      02-ticket.md         ◄── prompt source of truth        │
│    evals/                                                   │
│      ticket_agent/                                          │
│        login-issues.yaml  ◄── multi-turn dataset items      │
│        billing.yaml                                         │
│      knowledge_agent/                                       │
│        faq-lookups.yaml                                     │
│    schemas/                                                 │
│      ticket-output.json                                     │
│                                                             │
│  domains/sales/                                             │
│    prompts/                                                 │
│      01-coordinator.md                                      │
│      02-lead-qual.md                                        │
│    evals/                                                   │
│      lead_qualification_agent/                              │
│        hot-leads.yaml                                       │
│        cold-leads.yaml                                      │
│        edge-cases.yaml                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │  PR touches prompts/ or evals/
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    CI Pipeline (GitHub Actions)              │
│                                                             │
│  1. Detect affected agents                                  │
│  2. Sync YAML → Langfuse datasets                           │
│  3. Run LLM-only eval (Option B)                            │
│  4. Score: deterministic + LLM-as-judge                     │
│  5. Compare vs. main branch baseline                        │
│  6. Post PR comment with results                            │
│  7. Gate merge on regression thresholds                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Langfuse                                  │
│                                                             │
│  Datasets         → one per sub-agent                       │
│  Dataset Items    → multi-turn conversations from YAML      │
│  Dataset Runs     → one per CI execution (tagged with SHA)  │
│  Scores           → deterministic + LLM-judge per item      │
│  Dashboard        → compare runs across prompt versions     │
│                                                             │
│  Production traces → tagged for feedback loop               │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Prompt source of truth | GitHub (no change) | Avoids fragmenting source of truth; no sync headaches with external prompt platforms |
| Eval backend | Langfuse (not custom) | Already used for observability; has native dataset/run/score primitives |
| Agent invocation mode | Option B: LLM-only | Sends prompt + messages + tool schemas to LLM directly; no LangGraph/tool execution needed. Fast, cheap, isolates prompt quality |
| Dataset granularity | Multi-turn per sub-agent | Tests agents at the boundary they operate at — after handoff, with real conversation context |

---

## 3. Multi-Turn Datasets Per Sub-Agent

Each sub-agent gets its own Langfuse dataset. A dataset item is a **full conversation history** representing a realistic interaction with that agent post-handoff.

### Why Multi-Turn Matters

Agents don't receive cold single prompts. A `ticket_agent` gets conversation history from the coordinator, with context built up over multiple turns. Evaluating single-turn misses:

- Whether the agent picks up urgency signals from earlier messages
- Whether it avoids re-asking for information already provided
- Whether it handles multi-step workflows (validate email → create ticket → confirm)

### Dataset File Structure

```
domains/customer-support/
  evals/
    ticket_agent/
      login-issues.yaml        # 5-8 multi-turn scenarios
      billing-disputes.yaml    # 5-8 scenarios
      urgent-escalations.yaml  # edge cases around priority
    knowledge_agent/
      faq-lookups.yaml
      no-article-found.yaml
      handoff-triggers.yaml
domains/sales/
  evals/
    lead_qualification_agent/
      hot-leads.yaml
      cold-leads.yaml
      edge-cases.yaml
```

Grouping by **theme** (not just by agent) makes coverage visible at a glance — you can see you have 6 billing scenarios but zero scenarios for "user provides wrong email format."

### Dataset Item Format (YAML)

```yaml
dataset: ticket_agent
items:
  - id: "login-001"
    name: "Urgent login lockout"
    messages:
      - role: user
        content: "My login is broken after I reset my password yesterday"
      - role: assistant
        content: "I'm sorry about that. What email is on your account?"
      - role: user
        content: "alice@example.com"
      - role: user
        content: "This is urgent — client demo in 2 hours"
    expected:
      tool_calls:
        - name: create_ticket
          args_contains:
            priority: "high"
      judgments:
        - "Agent recognized urgency from the 2-hour deadline"
        - "Agent set ticket priority to high or critical"

  - id: "login-002"
    name: "Vague complaint — should clarify"
    messages:
      - role: user
        content: "Something is wrong with my account"
    expected:
      no_tool_calls: [create_ticket]
      judgments:
        - "Agent asks at least one clarifying question"
        - "Agent does not create a ticket without understanding the issue"

  - id: "login-003"
    name: "Multi-step: validate then create"
    messages:
      - role: user
        content: "I can't log in, my email is alice@example.com"
      - role: assistant
        content: "Let me verify that email and look into this."
      - role: user
        content: "Yes please create a ticket for this"
    expected:
      tool_calls:
        - name: validate_email
          args_contains:
            email: "alice@example.com"
        - name: create_ticket
      tool_order: strict
      judgments:
        - "Agent validated email before creating the ticket"
        - "Agent confirmed the ticket ID back to the user"
```

### Format Notes

- **`messages`** — the conversation as it arrives at the sub-agent after handoff. Authored from the sub-agent's perspective, not from session start.
- **`expected.tool_calls`** — list of tool calls the agent should make. `args_contains` is a partial match (you care about priority being "high", not the exact title string).
- **`expected.no_tool_calls`** — tools the agent should NOT invoke in this scenario.
- **`expected.tool_order`** — `strict` means tool calls must appear in the specified order; `any` (default) means order doesn't matter.
- **`expected.judgments`** — natural language criteria passed to an LLM judge along with the actual response.

---

## 4. Eval Runner (LLM-Only — Option B)

The eval runner sends the agent's system prompt + tool schemas + conversation history directly to the LLM. No LangGraph, no ToolRuntime, no context_store. It evaluates **"did the LLM make the right choices given this prompt and conversation?"**

### Per-Item Execution Flow

```
For each dataset item:

  1. Load system prompt markdown
     └── from prompts/{agent_prompt_ref}.md (as specified in agents.yaml)

  2. Load tool schemas for the agent
     └── from agents.yaml tool list → tool_registry → extract JSON schemas
     └── tools are passed as definitions only — nothing is executed

  3. Construct messages array
     └── [system_prompt] + dataset item's conversation history

  4. Call LLM (single completion, not streaming)
     └── model configured per agent or globally

  5. Capture response
     └── text content + any tool_use blocks

  6. Score response
     └── deterministic checks + LLM-as-judge

  7. Push scores to Langfuse
     └── attached to dataset run + item
```

### Tool Schema Injection

Since agents have tools defined in `agents.yaml`, the runner extracts tool JSON schemas so the LLM can express tool decisions. It does NOT need actual tool implementations.

```python
# Conceptual — extract schemas from tool_registry
def get_tool_schemas(agent_name: str) -> list[dict]:
    """Load tool JSON schemas for an agent (no implementations needed)."""
    agent_config = load_agents_yaml()[agent_name]
    schemas = []
    for tool_name in agent_config["tools"]:
        if tool_name in ("handoff", "get_agent_list"):
            schemas.append(FRAMEWORK_TOOL_SCHEMAS[tool_name])
        else:
            lc_tool = tool_registry.get(tool_name)
            schemas.append(lc_tool.get_input_schema())
    return schemas
```

This matters because a major part of what you're evaluating is **tool selection** — did the agent choose `create_ticket` vs. `handoff` vs. asking a follow-up question?

---

## 5. Scoring Functions

Three categories, all pushing scores back to the Langfuse dataset run.

### 5.1 Deterministic Scores (cheap, fast, every eval)

| Score Name | What It Checks | Type |
|------------|---------------|------|
| `tool_called` | Did the response include a tool_use block with the expected tool name? | Binary |
| `tool_args_match` | Do tool call arguments contain the expected key-value pairs? (partial match) | Binary |
| `tool_not_called` | Agent avoided calling tools in the `no_tool_calls` list? | Binary |
| `tool_order` | If `strict`, did tool calls appear in the specified sequence? | Binary |
| `schema_valid` | Does structured output match the agent's `output_schema` JSON schema? | Binary |
| `response_not_empty` | Agent produced a non-empty text response? | Binary |

**Aggregate:** `deterministic_pass_rate` — percentage of deterministic checks that passed across all items.

### 5.2 LLM-as-Judge Scores (per judgment criterion)

For each string in `expected.judgments`, the runner asks a judge LLM:

```
Given this conversation history and this agent response,
evaluate whether the following criterion is met:

"{judgment}"

Respond with:
- score: 0 (not met) or 1 (met)
- reasoning: one sentence explaining why
```

**Model choice for judging:** Use a cheaper/faster model (e.g., GPT-4o-mini, Haiku) since the judgment criteria are specific enough that the most powerful model isn't needed.

**Aggregate:** `judge_score` — average across all judgment criteria for an item. `judge_pass_rate` — percentage of items where all judgments scored 1.

### 5.3 Run-Level Aggregates

| Metric | Definition |
|--------|-----------|
| `pass_rate` | % of items where ALL deterministic checks passed |
| `judge_avg` | Mean LLM-judge score across all items |
| `regression_delta` | Difference vs. last scored run on main branch |

---

## 6. Langfuse Integration Mapping

| Dynagent Concept | Langfuse Concept | Notes |
|-----------------|-----------------|-------|
| Sub-agent (ticket_agent) | Dataset | One dataset per sub-agent |
| YAML eval item (login-001) | Dataset Item | Input = messages, Expected Output = expected block |
| One CI run on a PR | Dataset Run | Tagged with git SHA + branch |
| Deterministic check result | Score (numeric) | Attached to run item |
| LLM-judge result | Score (numeric) | Attached to run item |
| Git commit SHA | Run metadata | Enables cross-version comparison |
| Branch name | Run metadata | Distinguishes main vs. PR runs |

### What This Enables in the Dashboard

- Compare runs across commits for the same dataset
- See which specific items regressed (drill into login-001 to see the full messages + response + per-judgment scores)
- Track score trends over time as prompts evolve
- Filter by branch to see main vs. feature branch performance

---

## 7. CI Pipeline

### Trigger

GitHub Action triggers when a PR modifies files under `prompts/` or `evals/`.

### Flow

```
PR touches prompts/02-ticket.md
  │
  ├── 1. Detect affected agents
  │     └── prompt change to 02-ticket.md → ticket_agent (via agents.yaml mapping)
  │
  ├── 2. Sync YAML eval files → Langfuse datasets
  │     └── upsert dataset items, tag with git commit SHA
  │
  ├── 3. Run eval for each affected agent
  │     └── LLM-only invocation per dataset item (Option B)
  │
  ├── 4. Score all items
  │     └── deterministic + LLM-as-judge
  │
  ├── 5. Push scores to Langfuse as a new dataset run
  │     └── metadata: { branch, commit_sha, pr_number }
  │
  ├── 6. Fetch baseline scores from last main branch run
  │
  ├── 7. Compare and post PR comment
  │
  └── 8. Pass/fail gate
```

### PR Comment Format

```
🧪 Prompt Eval Results — ticket_agent

                        main (abc123)    PR (def456)    Δ
tool_sequence_match     92%              88%            -4% ⚠️
schema_valid            100%             100%            —
urgency_detection       78%              91%            +13% ✅
completeness            85%              87%            +2% ✅

⚠️ tool_sequence_match regressed — check: billing-disputes #3, #5

Langfuse run: https://langfuse.example.com/runs/abc123
```

### Merge Gate Rules

| Condition | Action |
|-----------|--------|
| `deterministic_pass_rate` drops below threshold (e.g., 90%) | Block merge |
| Any deterministic check regresses vs. main | Warn (configurable: block or warn) |
| `judge_avg` drops by > X% | Warn |
| New eval items added (no baseline) | Info only, no gate |

---

## 8. Production Feedback Loop

Long-term play: use Langfuse production traces to grow eval datasets organically.

### Flow

```
Production conversation (Langfuse trace)
  │
  ├── QA/Product tags trace as "interesting"
  │     └── failure, edge case, surprisingly good response
  │
  ├── Export script converts tagged trace → YAML eval item
  │     └── extracts message history, writes skeleton expected block
  │
  ├── Developer fills in expected.tool_calls and expected.judgments
  │
  └── Opens PR adding the new eval case
        └── now permanently covered in regression suite
```

### What This Achieves

After 3-6 months, the eval suite reflects **real user behavior** rather than developer imagination. Coverage grows from production reality.

### Langfuse Trace Tags for Feedback Loop

| Tag | Meaning | Action |
|-----|---------|--------|
| `eval:failure` | Agent made a clear mistake | Export as negative test case |
| `eval:edge-case` | Unusual scenario worth covering | Export as boundary test case |
| `eval:exemplary` | Agent handled this perfectly | Export as positive regression case |
| `eval:ambiguous` | Unclear if agent did the right thing | Review with team, then decide |

---

## 9. Implementation Phases

### Phase 1: Foundation (1-2 days)

**Goal:** Manually runnable eval for one agent.

- Define YAML format and write 5-10 dataset items for `ticket_agent`
- Build eval runner CLI: `make eval agent=ticket_agent`
- Deterministic scoring only (tool_called, args_match, schema_valid)
- Output: results printed to stdout, no Langfuse yet

**Exit criteria:** Can run `make eval agent=ticket_agent` and get a pass/fail table.

### Phase 2: Langfuse Integration (2-3 days)

**Goal:** Scores tracked and comparable in Langfuse.

- Sync YAML → Langfuse datasets (upsert logic)
- Push scores to Langfuse dataset runs
- Tag runs with git SHA and branch
- Add LLM-as-judge scoring

**Exit criteria:** Can view and compare eval runs in Langfuse dashboard.

### Phase 3: CI Integration (2-3 days)

**Goal:** Prompt changes are automatically evaluated on PR.

- GitHub Action triggered by prompt/eval file changes
- Detects affected agents from file paths + agents.yaml
- Runs eval, compares vs. main baseline
- Posts PR comment with results table
- Configurable merge gate

**Exit criteria:** PR that modifies a prompt gets an automated eval comment.

### Phase 4: Production Loop (ongoing)

**Goal:** Eval datasets grow from production.

- Trace tagging conventions in Langfuse
- Export script: tagged trace → YAML eval item skeleton
- Team process for reviewing and merging new eval cases

**Exit criteria:** At least 5 eval cases added from production traces per month.

---

## 10. CLI Interface

```bash
# Run eval for a specific agent
make eval agent=ticket_agent

# Run eval for all agents in a domain
make eval domain=customer-support

# Run eval and sync to Langfuse
make eval agent=ticket_agent sync=true

# Run eval comparing against a baseline commit
make eval agent=ticket_agent baseline=main

# Export a Langfuse trace to YAML eval item
make eval-export trace_id=abc123 agent=ticket_agent
```

### Underlying Commands

```bash
# CLI entrypoint
python -m dynagent.eval run \
  --agent ticket_agent \
  --eval-dir domains/customer-support/evals/ticket_agent/ \
  --prompt-dir domains/customer-support/prompts/ \
  --sync-langfuse \
  --tag "branch=feature/better-urgency,sha=$(git rev-parse HEAD)"
```

---

## 11. Open Questions

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | LLM-judge model | Same model as agent vs. cheaper judge model | Cheaper (e.g., Haiku) — judgment criteria are specific enough |
| 2 | Eval on every PR vs. on-demand | Always run vs. manual trigger | Always run when prompt/eval files change; on-demand for other PRs |
| 3 | Shared eval cases across agents | Some scenarios test coordinator + sub-agent together | Defer — start with per-sub-agent, add integration evals in Phase 4+ |
| 4 | Non-determinism handling | Same prompt can produce different tool call patterns | Run each item N times (e.g., 3), report pass rate across runs |
| 5 | Cost budget for CI evals | LLM calls cost money | Cap at ~50 items per agent per PR; nightly full suite |
