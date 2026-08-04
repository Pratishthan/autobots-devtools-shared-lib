# Agno Cookbook vs shared-lib Comparison Doc — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/design/agno-comparison.md` — a capability matrix and gap analysis of shared-lib (Dynagent 0.11.0b2) against the Agno cookbook, with build/adopt/skip verdicts per gap.

**Architecture:** This is a research-and-writing project, not a code project. One Markdown deliverable is built up section by section; each task researches one slice (via WebFetch on GitHub + reading local shared-lib source) and appends to the doc. "Tests" are validation greps and checklist passes instead of pytest.

**Tech Stack:** Markdown, WebFetch/`gh api` for Agno research, Read/Grep on `src/autobots_devtools_shared_lib/` for parity claims.

**Spec:** `docs/superpowers/specs/2026-08-04-agno-comparison-design.md` — read it before starting. The rubrics there are normative.

## Global Constraints

- Doc-only: no code changes, no spikes, no tickets.
- All paths below are relative to the repo root `autobots-devtools-shared-lib/`. Run all git commands from inside this repo (pre-commit hooks require it), on branch `main`.
- Framing is supplement-not-replace: Dynagent's LangChain/LangGraph core is not up for replacement. Never write a verdict that proposes replacing the engine.
- Open-source Agno library only; ignore Agno's commercial/cloud offerings (agno.com platform, pricing pages).
- Parity ratings must be exactly one of: `has`, `partial`, `missing`, `n-a` (spec defines each).
- Verdicts must be exactly one of: **build**, **adopt** (+ integration mode: pattern-borrow / library dep / sidecar), **skip**.
- Parity claims cite real modules under `src/autobots_devtools_shared_lib/` — verify each cited path exists before writing it. Planned-but-unbuilt work rates `missing`/`partial`, never `has`.
- Commit after every task with the `docs:` prefix.

---

### Task 1: Doc skeleton with Context & Method

**Files:**
- Create: `docs/design/agno-comparison.md`
- Read: `docs/superpowers/specs/2026-08-04-agno-comparison-design.md`

**Interfaces:**
- Produces: the doc with five `##` section headers (exact titles below) that all later tasks append under; the pinned Agno commit SHA recorded in section 1.

- [ ] **Step 1: Pin the Agno commit and enumerate cookbook sections**

Run:
```bash
gh api repos/agno-agi/agno/commits/main --jq '.sha + " " + .commit.committer.date'
gh api repos/agno-agi/agno/contents/cookbook --jq '.[] | select(.type=="dir") | .name'
```
Expected: a 40-char SHA + date, and a directory list similar to `00_quickstart, 01_demo, 02_agents, 03_teams, 04_workflows, 05_agent_os, 06_storage, 07_knowledge, 08_learning, 09_evals, 10_reasoning, 11_memory, 12_context, 13_filesystem, 90_models, 91_tools, 93_components` (plus possibly others). Save both outputs — the directory list is the authoritative row list for the matrix; if it differs from the list above, the actual list wins.

- [ ] **Step 2: Write the skeleton**

Create `docs/design/agno-comparison.md`:

```markdown
# Agno Cookbook vs shared-lib: Capability Comparison

**Date:** <today>
**shared-lib version:** 0.11.0b2
**Agno pinned commit:** `<sha>` (main as of <date from step 1>)
**Spec:** [design spec](../superpowers/specs/2026-08-04-agno-comparison-design.md)

## 1. Context & method

Compared: the [Agno cookbook](https://github.com/agno-agi/agno/tree/main/cookbook) at the pinned
commit above vs `autobots-devtools-shared-lib` at HEAD. Goal: (a) find capabilities Agno
demonstrates that Dynagent lacks, to prioritize the roadmap; (b) evaluate where Agno can
**supplement** Dynagent. Agno is not a replacement candidate; the LangChain/LangGraph core stays.

Method: shallow pass over every cookbook section (section README/index, drilling into examples only
where ambiguous; Agno docs/source consulted where the cookbook is marketing-thin — such rows are
marked "rated from source"). Shared-lib parity claims come from reading code under
`src/autobots_devtools_shared_lib/`, cited per row.

**Parity rubric:** `has` = equivalent exists and is used by at least one app (MER, Pay, Jarvis) ·
`partial` = exists but narrower/experimental · `missing` = nothing comparable · `n-a` = doesn't
apply to this architecture. Planned-but-unbuilt work rates `missing`/`partial` with a pointer to
its design doc.

**Verdict rubric (deep-dives):** **build** when the gap touches Dynagent's core loop (LangGraph
state, middleware, config) · **adopt** (pattern-borrow / library dep / sidecar) when cleanly
separable · **skip** when no consuming app has a driving use case.

## 2. Capability matrix

| Agno section | What Agno demonstrates | shared-lib equivalent | Rating |
|--------------|------------------------|-----------------------|--------|

## 3. Gap deep-dives

## 4. Dynagent-only capabilities

## 5. Roadmap summary

## Appendix A: shared-lib module inventory
```

- [ ] **Step 3: Verify skeleton**

Run: `grep -c '^## ' docs/design/agno-comparison.md`
Expected: `6` (five numbered sections + appendix).

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: skeleton for Agno comparison doc (context, method, rubrics)"
```

---

### Task 2: shared-lib module inventory (Appendix A)

**Files:**
- Modify: `docs/design/agno-comparison.md` (Appendix A)
- Read: everything under `src/autobots_devtools_shared_lib/`

**Interfaces:**
- Consumes: doc skeleton from Task 1.
- Produces: Appendix A — a table with columns `Module | Capability (one line) | Key entry points`, one row per subpackage. Matrix rows in Tasks 3–5 cite modules by the exact paths listed here.

- [ ] **Step 1: Enumerate subpackages**

Run:
```bash
find src/autobots_devtools_shared_lib -maxdepth 2 -type d -not -path '*__pycache__*'
```
Expected (verify against reality): `dynagent/` (with `agents`, `middleware`, `tools`, `llm`, `config`, `models`, `api`, `services`, `ui`, `utils`), `eval/` (with `core`, `assertions`, `scoring`, `models`, `pytest_plugin`), `dynadoc/`, `common/` (with `tools`, `config`, `utils`, `observability`, `servers`, `services`).

- [ ] **Step 2: Read each subpackage's `__init__.py` and main modules; fill Appendix A**

For each directory from step 1, read its `__init__.py` (public exports) and skim the largest module in it, then add one table row. Example row shape (write real content, not this example, after reading the code):

```markdown
| `dynagent/agents` | Agent construction from YAML config (`create_base_agent`) | `create_base_agent`, `invoke_agent`, `ainvoke_agent` |
```

Also read `CONTEXT.md` at the repo root — it holds the project glossary and prevents misnaming capabilities.

- [ ] **Step 3: Verify every cited path exists**

Run:
```bash
grep -o '`[a-z_]*/[a-z_/]*`' docs/design/agno-comparison.md | tr -d '`' | sort -u | while read p; do [ -e "src/autobots_devtools_shared_lib/$p" ] || echo "MISSING: $p"; done
```
Expected: no `MISSING:` lines.

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: shared-lib module inventory appendix for Agno comparison"
```

---

### Task 3: Matrix rows — core agent surface (sections 00–05)

**Files:**
- Modify: `docs/design/agno-comparison.md` (section 2 table)

**Interfaces:**
- Consumes: Appendix A module paths (cite these verbatim); row list pinned in Task 1 section 1.
- Produces: one matrix row per cookbook section `00_quickstart`, `01_demo`, `02_agents`, `03_teams`, `04_workflows`, `05_agent_os` (adjust names to the Task 1 listing). Row format is fixed by the table header from Task 1.

- [ ] **Step 1: Research the six sections**

For each section, WebFetch `https://github.com/agno-agi/agno/tree/main/cookbook/<section>` asking: "What capabilities do the examples in this directory demonstrate? List them concretely (APIs, patterns), not marketing language." Drill into a subdirectory or file only if the listing alone is ambiguous. If a section is marketing-thin, consult `https://docs.agno.com` for that topic and note "rated from docs" in the row.

- [ ] **Step 2: Write the six rows**

For each: name the closest shared-lib equivalent from Appendix A (or "none"), pick a rating per the rubric. Example row shape (write real researched content):

```markdown
| `03_teams` | Multi-agent coordination modes (route/collaborate/coordinate) | `dynagent/agents` handoff + `get_agent_list` tools | `partial` |
```

Remember: `has` requires at least one consuming app (MER, Pay, Jarvis) actually using it — check the app repos' `agent_configs/` and `domains/` if unsure (`../autobots-agents-mer/`, `../autobots-agents-pay/`, `../autobots-agents-jarvis/`).

- [ ] **Step 3: Verify row count and rating validity**

Run:
```bash
grep -c '^| `0[0-5]' docs/design/agno-comparison.md
grep '^| `' docs/design/agno-comparison.md | grep -vE '\| `(has|partial|missing|n-a)` \|$'
```
Expected: `6` from the first command; the second prints only the table header line (every data row must end in a valid backticked rating).

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: Agno comparison matrix rows 00-05 (core agent surface)"
```

---

### Task 4: Matrix rows — state, knowledge & cognition (sections 06–13)

**Files:**
- Modify: `docs/design/agno-comparison.md` (section 2 table)

**Interfaces:**
- Consumes: Appendix A paths; same fixed row format.
- Produces: one row per section `06_storage`, `07_knowledge`, `08_learning`, `09_evals`, `10_reasoning`, `11_memory`, `12_context`, `13_filesystem` (adjust to Task 1 listing).

- [ ] **Step 1: Research the eight sections**

Same procedure as Task 3 step 1. Two sections need extra care:
- `08_learning`: determine from Agno source (`gh api repos/agno-agi/agno/contents/libs/agno/agno --jq '.[].name'`, then drill in) whether "learning" is a real subsystem (modules, storage schema) or a prompt pattern — record which in the row.
- `09_evals`: compare against shared-lib `eval/` (assertions, scoring, pytest_plugin) specifically — this is one of the likelier `has`/`partial` rows and the row must say what each side covers.

- [ ] **Step 2: Write the eight rows**

Same format as Task 3 step 2. For memory/knowledge rows, planned shared-lib work (episodic memory research, `docs/design/Memory-1-session.md` in the MER repo) rates `missing`/`partial` with a pointer — plans are not parity.

- [ ] **Step 3: Verify row count and rating validity**

Run:
```bash
grep -c '^| `\(0[6-9]\|1[0-3]\)' docs/design/agno-comparison.md
```
Expected: `8`. Re-run the rating-validity grep from Task 3 step 3; expected no output.

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: Agno comparison matrix rows 06-13 (state, knowledge, cognition)"
```

---

### Task 5: Matrix rows — infrastructure (sections 90+) and any extras

**Files:**
- Modify: `docs/design/agno-comparison.md` (section 2 table)

**Interfaces:**
- Consumes: Appendix A paths; the authoritative directory list from Task 1.
- Produces: one row per remaining cookbook section (`90_models`, `91_tools`, `93_components`, plus every directory from the Task 1 listing not yet covered by Tasks 3–4). After this task the matrix is complete.

- [ ] **Step 1: Diff covered rows against the Task 1 listing**

List sections already in the table, compare with the Task 1 directory listing, and enumerate what remains. Every remaining directory gets a row — including ones not in the nominal list (integrations, observability, etc.).

- [ ] **Step 2: Research and write the remaining rows**

Same procedure and format as Task 3. `90_models` is a likely `n-a` candidate (multi-provider matrix vs standardized provider) — but verify what `dynagent/llm` actually supports before rating.

- [ ] **Step 3: Verify matrix completeness**

Count table rows vs the Task 1 directory listing count — they must match exactly. Re-run the rating-validity grep from Task 3 step 3; expected no output.

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: complete Agno comparison matrix (infra rows + extras)"
```

---

### Task 6: Gap deep-dives with verdicts (section 3)

**Files:**
- Modify: `docs/design/agno-comparison.md` (section 3)

**Interfaces:**
- Consumes: the completed matrix — every `missing`/`partial` row is a deep-dive candidate.
- Produces: one `###`-level subsection per actionable gap using the fixed template below; plus, at the top of section 3, a one-line-per-row list of `missing`/`partial` rows judged *not* actionable, each with its reason.

- [ ] **Step 1: Triage the gaps**

List every `missing`/`partial` row. For each, decide actionable vs not: actionable means at least one consuming app (MER, Pay, Jarvis) has a plausible near-term use. Write the not-actionable list first (row name + one-line reason).

- [ ] **Step 2: Write one deep-dive per actionable gap**

Fixed template — every deep-dive uses exactly this shape:

```markdown
### Gap: <capability name> (from `<agno section>`)

**What Agno provides:** <2-4 sentences, concrete: APIs, storage, patterns.>

**Why it matters here:** <which app (MER/Pay/Jarvis) would use it and for what.>

**Verdict: <build | adopt (pattern-borrow | library dep | sidecar) | skip>**

<2-5 sentences of reasoning. For adopt: why that integration mode. For build: why it belongs in
Dynagent's core. For skip: what would have to change to revisit.>
```

Apply the verdict rubric from section 1. Exactly one verdict per deep-dive.

- [ ] **Step 3: Verify coverage**

For every `missing`/`partial` row in the matrix, confirm it appears either as a deep-dive or in the not-actionable list. Run `grep -c '^### Gap:' docs/design/agno-comparison.md` and `grep -c '\*\*Verdict:' docs/design/agno-comparison.md` — counts must be equal.

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: Agno comparison gap deep-dives with build/adopt/skip verdicts"
```

---

### Task 7: Dynagent-only capabilities (section 4) and roadmap summary (section 5)

**Files:**
- Modify: `docs/design/agno-comparison.md` (sections 4 and 5)

**Interfaces:**
- Consumes: Appendix A (candidate Dynagent-only capabilities), completed matrix + deep-dives.
- Produces: section 4 as a short table `Capability | Where | Why Agno's cookbook has no equivalent`; section 5 as a table `Gap | Verdict | Mode (if adopt) | Suggested priority (P1-P3)` with one row per deep-dive from Task 6.

- [ ] **Step 1: Write section 4**

Walk Appendix A and list capabilities with no cookbook counterpart. Verify each against the matrix (it must not already appear as an Agno-side capability). Candidates to check — confirm in code before listing: `dynadoc/` (doc-canvas rendering), YAML config-first agent definitions (`dynagent/config`), `eval/pytest_plugin` (evals as pytest tests), `common/servers/fileserver` + `noderedmanagerserver`, isolated-history middleware (`dynagent/middleware`).

- [ ] **Step 2: Write section 5**

One row per Task 6 deep-dive, copying the verdict verbatim. Assign P1–P3 by: P1 = an app needs it this quarter; P2 = clear future need; P3 = nice-to-have. Order rows P1 first. Skip-verdict gaps go in the table too (priority `—`) so the summary is a complete record.

- [ ] **Step 3: Verify verdict consistency**

Every verdict string in section 5 must match its deep-dive in section 3 exactly (same verdict, same mode). Check by reading both sections side by side.

- [ ] **Step 4: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: Dynagent-only capabilities and roadmap summary for Agno comparison"
```

---

### Task 8: Final validation pass

**Files:**
- Modify: `docs/design/agno-comparison.md` (fixes only)

**Interfaces:**
- Consumes: the complete doc.
- Produces: the doc passing the spec's validation checklist; final commit.

- [ ] **Step 1: Run the spec's validation checklist**

From the spec, verify each item and fix inline where broken:
1. Every matrix row cites a real shared-lib module or explicitly says "none" — re-run the path-existence check from Task 2 step 3.
2. Every `missing`/`partial` row has a deep-dive or a one-line not-actionable reason (Task 6 step 3 check).
3. Every deep-dive ends in exactly one verdict (`grep -c '^### Gap:'` equals `grep -c '\*\*Verdict:'`).
4. Row count equals the Task 1 cookbook directory count.
5. No `TBD`/`TODO`/placeholder text: `grep -inE 'TBD|TODO|FIXME|\?\?\?' docs/design/agno-comparison.md` returns nothing.

- [ ] **Step 2: Read the doc top to bottom once**

Check the two framing constraints hold everywhere: no verdict proposes replacing the engine; no commercial-offering evaluation crept in. Fix any drift.

- [ ] **Step 3: Commit**

```bash
git add docs/design/agno-comparison.md
git commit -m "docs: final validation pass on Agno comparison doc"
```
