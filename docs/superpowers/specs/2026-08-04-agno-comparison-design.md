# Agno Cookbook vs shared-lib: Comparison Doc — Design Spec

**Date:** 2026-08-04
**Status:** Approved design, pending implementation
**Deliverable:** `docs/design/agno-comparison.md` (this repo)

## Purpose

Produce a gap analysis of `autobots-devtools-shared-lib` (Dynagent framework, 0.11.0b2)
against the [Agno cookbook](https://github.com/agno-agi/agno/tree/main/cookbook), with two goals:

1. Identify capabilities Agno demonstrates that Dynagent lacks, to prioritize the shared-lib roadmap.
2. Evaluate where Agno could **supplement** Dynagent. Agno is not a replacement candidate;
   Dynagent's LangChain/LangGraph core stays.

Scope decision: all ~17 cookbook areas get a shallow pass first; only actionable gaps get deep-dives.

## Deliverable structure

One document: `docs/design/agno-comparison.md`, with five sections.

1. **Context & method** — what was compared (Agno cookbook pinned to the `main` commit on the
   comparison date; shared-lib 0.11.0b2), the supplement-not-replace framing, and both rubrics below.
2. **Capability matrix** — one row per cookbook section (~17 rows):
   what Agno demonstrates → shared-lib equivalent (module-level pointers into
   `dynagent/`, `eval/`, `dynadoc/`, `common/`) → parity rating.
3. **Gap deep-dives** — one subsection per actionable gap: what Agno provides, why it matters
   for the consuming apps (MER, Pay, Jarvis), and exactly one verdict —
   **build natively / adopt Agno / skip** — with reasoning. Adopt verdicts name an integration mode:
   pattern-borrow, library dependency, or sidecar service.
4. **Dynagent-only capabilities** — what shared-lib has that the cookbook does not cover
   (dynadoc, YAML config-first agents, eval pytest plugin, file-server backend, etc.).
5. **Roadmap summary** — a prioritized table of the build/adopt verdicts, ready for grooming.

## Method & data sources

- **Agno side:** read the cookbook on GitHub section by section — each section's README/index,
  drilling into individual examples only where the index is ambiguous. Consult Agno's docs site
  where the cookbook alone doesn't make a capability's depth clear (e.g., whether "learning" is a
  real subsystem or a pattern). Record the pinned commit/date in the doc.
- **Shared-lib side:** parity claims come from reading the actual code under
  `src/autobots_devtools_shared_lib/` — not from memory or CLAUDE.md — so each matrix row cites
  real modules.

## Rubrics

**Parity rating (matrix):**

| Rating | Meaning |
|--------|---------|
| `has` | Equivalent capability exists and is used by at least one app |
| `partial` | Exists but narrower or experimental |
| `missing` | Nothing comparable |
| `n-a` | Doesn't apply to this architecture (e.g., a 40-provider model matrix when standardized on one provider) |

**Verdict (deep-dives):**

- **build** — preferred when the gap touches Dynagent's core loop (LangGraph state, middleware, config).
- **adopt** — preferred when the capability is cleanly separable (knowledge stores, eval scoring ideas);
  must name the integration mode (pattern-borrow / library dep / sidecar).
- **skip** — when no consuming app has a driving use case. YAGNI applies to gaps too.

## Scope boundaries

- No code changes, no spikes, no tickets — doc only.
- Open-source Agno library only; no evaluation of Agno's commercial/cloud offerings.
- No re-litigating classic-engine vs deepagents — this compares capabilities, not engines.

## Edge cases

- Cookbook sections that are marketing-thin get their rating from Agno source/docs instead, noted as such.
- Capabilities that are planned but not built in shared-lib (e.g., episodic memory research) rate
  `missing`/`partial` with a pointer to the design doc — plans do not count as parity.

## Validation (self-review checklist for the comparison doc)

- Every matrix row cites a real shared-lib module, or explicitly states none exists.
- Every `missing`/`partial` row either has a deep-dive or a one-line reason it is not actionable.
- Every deep-dive ends in exactly one verdict.
