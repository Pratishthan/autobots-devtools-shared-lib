# Agno Cookbook vs shared-lib: Capability Comparison

**Date:** 2026-08-04
**shared-lib version:** 0.11.0b2
**Agno pinned commit:** `21d274d63052a229fccd6b2621ea2a7da8eb1527` (main as of 2026-08-03)
**Spec:** [design spec](../superpowers/specs/2026-08-04-agno-comparison-design.md)

## 1. Context & method

Compared: the [Agno cookbook](https://github.com/agno-agi/agno/tree/main/cookbook) at the pinned
commit above vs `autobots-devtools-shared-lib` at HEAD. Goal: (a) find capabilities Agno
demonstrates that Dynagent lacks, to prioritize the roadmap; (b) evaluate where Agno can
**supplement** Dynagent. Agno is not a replacement candidate; the LangChain/LangGraph core stays.

Method: shallow pass over every cookbook section (section README/index, drilling into examples only
where ambiguous; Agno docs/source consulted where the cookbook is marketing-thin — such rows are
marked "rated from docs" or "rated from source"). Shared-lib parity claims come from reading code
under `src/autobots_devtools_shared_lib/`, cited per row.

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
