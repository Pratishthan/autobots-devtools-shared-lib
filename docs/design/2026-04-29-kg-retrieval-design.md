# Design — Knowledge Graph Retrieval for Dynagent Agents

**Date:** 2026-04-29
**Repo:** `autobots-devtools-shared-lib` (new module `autobots_devtools_shared_lib.kg`)
**Status:** Draft

## Problem

KBE extracts a Knowledge Graph from FBP (Spring Boot) source — products, microservices, services, data models, behaviour configs, behaviours. Dynagent agents (Nurture, Designer, BRO) need to consume *relevant* portions of this KG to do their jobs:

- **Nurture** generates code from an LLD that already names specific service / data model / behaviour stable IDs. It needs the deterministic subgraph rooted at those IDs.
- **Designer** maps features to existing reusable services / data models. Needs semantic discovery, then structural expansion to verify fit.
- **BRO** decomposes business requirements into candidate microservices / services / models across the entire portfolio. Needs cross-product semantic discovery.

There is no shared retrieval primitive today. Each agent would otherwise reinvent storage choice, query API, and ingestion. We also want to avoid hard-coupling the agents to any one graph engine (Neo4j, Kuzu, …).

## Goals

- Single retrieval API consumed by Nurture, Designer, BRO — and any future agent.
- Engine-agnostic: swap Neo4j ↔ Kuzu without touching agent code.
- Two retrieval primitives: **structural** (deterministic graph traversal) and **semantic discovery** (vector-based).
- Idempotent ingestion from KBE artifacts, hash-gated to control LLM/embedding cost.
- Surface as Dynagent tools today; MCP server later as a purely additive entry point.

## Non-Goals (v1)

- Formal inference / RDF reasoning. Property graph + traversal only. Revisit when compliance/tag-propagation use cases (PII, PCI scope, capability subsumption) become real.
- MCP server surface. Architecture supports it; not built in v1.
- Comprehensive error handling and observability. Happy path only for v1; circle back before promoting beyond pilot use. Open questions to revisit: tool envelope vs. exception strategy, structured logs/counters, LLM/embedding retry policy, graceful degradation when KG is unreachable.
- KG schema design. The schema (node labels, edge types, properties) is owned by a parallel track. This design consumes whatever it produces.
- Performance/load tests; embedding-quality eval harness.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage form | Property graph (engine deferred) | Schema is fixed-ish; queries are structural traversals + vector search. RDF inference not needed for v1. |
| Engine v1 | Neo4j | Mature native vector index, ergonomic Cypher, Python tooling. Kuzu is a candidate later via the same port. |
| Coupling | Port + adapter (`KGStore` Protocol) | Cypher lives only in adapter; service / tools / loader call the port. Engine swap is a constructor change. |
| Retrieval primitives | Structural + Semantic discovery | Two distinct needs (deterministic subgraph vs. fuzzy match). Semantic returns IDs; structural expands. |
| Embedding text | LLM-summarized per node | Quality bet for first impressions. Cached by content hash. |
| Surface v1 | Dynagent `@tool` wrappers | Lowest friction; matches existing `register_usecase_tools` pattern. |
| Surface v2 | MCP server (footnote) | Same `KGService` underneath; new entry point only. Not built in v1. |
| Ingestion | Manual CLI loader, stable-ID list input | Strict by default; `--allow-stubs` for partial loads. |
| Embedder location | Own module (`kg/embedding/`) | Used by both loader (write-side) and `KGService` (query-side). Single source of truth for model choice. |
| Home repo | `autobots-devtools-shared-lib` | Shared-lib hosts tools and frameworks; KG retrieval is exactly that. All apps consume one implementation. |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Surface (v1):  Dynagent @tool wrappers                     │
│  Surface (v2):  MCP server (footnote — not in v1)           │
├─────────────────────────────────────────────────────────────┤
│  KGService     — read-only recipes                          │
├─────────────────────────────────────────────────────────────┤
│  KGStore (port) — Protocol over the graph engine            │
├─────────────────────────────────────────────────────────────┤
│  Adapters     — Neo4jKGStore (v1) | KuzuKGStore (later)     │
├─────────────────────────────────────────────────────────────┤
│  Loader (CLI) — pay-kg load --ids …                         │
└─────────────────────────────────────────────────────────────┘
```

`KGService` is **read-only at runtime**. All write paths (summarize → embed → upsert) go through the loader.

## Components

### Port — `kg/ports.py`

Two Protocols, split by capability. `KGService` only ever sees the read port; the loader composes both.

Returns plain dataclasses — never driver types.

**Domain types:**

```python
@dataclass(frozen=True)
class Node:
    stable_id: str
    label: str                              # e.g. "Service", "DataModel"
    properties: dict[str, Any]
    content_hash: str | None = None
    summary: str | None = None
    embedding_meta: dict[str, str] | None = None  # {"model_version": ..., "prompt_version": ...}

@dataclass(frozen=True)
class Edge:
    source_id: str
    target_id: str
    edge_type: str
    properties: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Subgraph:
    nodes: list[Node]
    edges: list[Edge]

@dataclass(frozen=True)
class Path:
    nodes: list[Node]
    edges: list[Edge]

@dataclass(frozen=True)
class ScoredNode:
    node: Node
    score: float

@dataclass(frozen=True)
class NodeSummary:
    stable_id: str
    label: str
    name: str
    summary: str
    key_properties: dict[str, Any]          # subset suitable for compact display

@dataclass(frozen=True)
class RequirementDecomposition:
    candidates: list[ScoredNode]
    candidate_subgraphs: dict[str, Subgraph]   # keyed by candidate stable_id
```

**Filter type** — typed, not free-form `dict`:

```python
@dataclass(frozen=True)
class NodeFilter:
    properties: dict[str, str | int | bool | None] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)
    exclude_ids: list[str] = field(default_factory=list)
```

Adapters translate `NodeFilter` to engine-specific predicates. Free-form `dict` filters are forbidden — keeps Cypher out of upper layers (enforced via type-check).

**Read port:**

```python
class KGReadStore(Protocol):
    def get_node(self, stable_id: str) -> Node | None: ...
    def neighbors(self, stable_id: str, edge_types: list[str] | None,
                  direction: Literal["out","in","both"]) -> list[Edge]: ...
    def traverse(self, stable_id: str, depth: int,
                 edge_types: list[str] | None,
                 direction: Literal["out","in","both"]) -> Subgraph: ...
    def find_paths(self, source: str, target: str, max_depth: int) -> list[Path]: ...
    def semantic_search(self, query_vec: list[float],
                        node_types: list[str] | None,
                        filters: NodeFilter | None,
                        k: int) -> list[ScoredNode]: ...
    def get_dependents(self, stable_id: str) -> list[Edge]: ...   # for tombstone safety
```

**Write port** (loader-only):

```python
class KGWriteStore(Protocol):
    def begin_batch(self) -> "KGBatch": ...      # context manager: commit on __exit__, rollback on exception

class KGBatch(Protocol):
    def upsert_node(self, node: Node) -> None: ...
    def upsert_edge(self, edge: Edge) -> None: ...
    def delete_node(self, stable_id: str, *, force: bool = False) -> list[Edge]:
        """Delete node. If incoming edges exist and force is False, raise
        DependentsExistError carrying the incoming Edge list. Returns the list
        of edges actually removed."""
    def diff_outgoing_edges(self, stable_id: str,
                            new_edges: list[Edge]) -> tuple[list[Edge], list[Edge]]:
        """Returns (to_add, to_remove). Caller applies via upsert_edge / delete on edges."""
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

**Concrete store** combines both:

```python
class KGStore(KGReadStore, KGWriteStore, Protocol): ...
```

`KGService` is constructed with `KGReadStore` (cannot upcast to write). Loader is constructed with `KGStore`.

### `Embedder` — `kg/embedding/`

Lightweight client used by both loader (write-side) and `KGService` (query-side). Single source of truth for embedding configuration.

```python
class Embedder(Protocol):
    @property
    def model_version(self) -> str: ...     # stamped onto every embedding for compatibility checks
    @property
    def dim(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

**Compatibility enforcement:** every embedding stored carries `model_version` (in `Node.embedding_meta`). On startup, `KGService` records its `embedder.model_version`; if a `semantic_search` result's stored embedding has a different model_version, the service logs and skips the result. Loader refuses to write if its `Embedder.model_version` mismatches embeddings already in the store unless `--reembed-all` is passed.

### `Neo4jKGStore` adapter — `kg/adapters/neo4j_store.py`

Implements `KGStore` (both read and write) for Neo4j 5.x. Owns: driver session pooling, Cypher, vector index management (one per node label), retry policy, transactional batches. Translates each port call to Cypher; never lets `neo4j.Record` escape.

### `KGService` — `kg/service.py`

Read-only business-level recipes. Composed with `KGReadStore` and `Embedder` — cannot reach write methods.

```python
class KGService:
    def __init__(self, store: KGReadStore, embedder: Embedder): ...

    def get_subgraph(self, stable_id: str, depth: int = 2,
                     edge_types: list[str] | None = None) -> Subgraph: ...
    def get_dependencies(self, service_id: str) -> Subgraph: ...
    def get_node_summary(self, stable_id: str) -> NodeSummary: ...
    def semantic_search(self, query: str, node_types: list[str] | None = None,
                        filters: NodeFilter | None = None, k: int = 10) -> list[ScoredNode]: ...
    def decompose_requirement(self, text: str) -> RequirementDecomposition: ...
    def impact_topdown(self, product_id: str) -> Subgraph: ...
    def impact_bottomup(self, node_id: str) -> Subgraph: ...
```

`semantic_search` here = embed query via `Embedder` → call `store.semantic_search` → re-rank → hydrate. `decompose_requirement` is a recipe composing `semantic_search` + `traverse`.

### Loader — `kg/loader/`

CLI entry: `kg-load --ids X,Y,Z [--allow-stubs] [--tombstone …] [--force] [--reembed-all]`.

Neutral binary name (no app-specific prefix); shared-lib hosts it, all consuming apps use the same command.

Modules:
- `artifact_reader.py` — reads KBE JSON files by stable ID.
- `summarizer.py` — per-node-type prompt → LLM → short intent paragraph. Cached by content hash.
- `differ.py` — content-hash gate + outgoing-edge diff.
- `pipeline.py` — orchestrates: read → diff → summarize → embed → upsert. Wraps the whole batch in `KGWriteStore.begin_batch()` for transactional rollback on failure.
- `cli.py` — argument parsing.

Loader uses the same `Embedder` instance as `KGService` (factory injection). Loader writes via the port; never bypasses to the adapter directly. All writes happen inside a `KGBatch` context manager so partial-failure rollback is enforced by the port, not by ad-hoc loader logic.

**Tombstone handling lives in the loader**, not in `delete_node`. Sequence:
1. Loader calls `read_store.get_dependents(stable_id)`.
2. If non-empty and `--force` not set: print dependents, exit non-zero.
3. Otherwise: open batch, call `batch.delete_node(stable_id, force=True)` (which still raises `DependentsExistError` if state changed mid-flight — defense in depth), commit.

### Tool wrappers — `kg/tools.py`

Thin `@tool` shims around `KGService` recipes. Registered into Dynagent via the existing `register_usecase_tools` pattern; consuming apps wire them in their `server.py` startup.

```python
@tool
def kg_get_subgraph(runtime: ToolRuntime[None, Dynagent],
                    stable_id: str, depth: int = 2) -> str:
    """Return the subgraph rooted at stable_id, JSON-serialized."""
    svc = get_kg_service()
    return _serialize(svc.get_subgraph(stable_id, depth))
```

One tool per service recipe. Same set of tools used by every consuming domain (Nurture, Designer, BRO, …).

## Data Flow

### Ingestion (offline, CLI)

```
KBE artifacts (JSON)
     │
     ▼
artifact_reader → differ (hash + edge diff)
                       │  (hash miss only)
                       ▼
                 summarizer (LLM) → embedder (Embedder) → KGStore.upsert_*
```

Per stable ID in the input list:

1. Read artifact → compute `content_hash`.
2. Compare to stored hash. Match → skip (no LLM, no embedding, no DB write).
3. Summarize via per-node-type prompt → `summary`.
4. Embed `summary` (+ structured fields) → `embedding`.
5. Upsert node `{properties, content_hash, summary, embedding, prompt_version, model_version}`.
6. Diff outgoing edges → DELETE removed, MERGE new.
7. Strict mode (default): any unresolved edge target → batch raises, `KGBatch.__exit__` rolls back. `--allow-stubs` creates `:Stub` placeholder.

The whole batch is wrapped in `with store.begin_batch() as batch:`; commit happens on clean exit. Any exception (LLM failure, embedder failure, unresolved reference) triggers rollback — no partial state visible.

Tombstones: loader pre-checks dependents via `KGReadStore.get_dependents`; refuses unless `--force`. See Loader §Tombstone handling.

### Retrieval — Nurture (structural)

```
LLD names urn:svc:kyc:VerifyIdentity
     │
     ▼
agent → @tool kg_get_subgraph(stable_id, depth=2)
     │
     ▼
KGService.get_subgraph → KGStore.traverse(...)
     │
     ▼
Subgraph(nodes, edges) → JSON → agent
```

No LLM, no embedding. Pure graph read.

### Retrieval — BRO (semantic + structural)

```
"let customers redeem loyalty points at checkout"
     │
     ▼
agent → @tool kg_decompose_requirement(text)
     │
     ▼
KGService.decompose_requirement:
  1. embedder.embed(text) → query_vec
  2. store.semantic_search(query_vec,
       node_types=[ProductMS,ComponentMS,Service,DataModel], k=20)
  3. re-rank by structural signals (in-degree, recency)
  4. for top-N hits: store.traverse(hit.id, depth=1)
  5. assemble RequirementDecomposition(candidates, candidate_subgraphs)
     │
     ▼
agent
```

Embedder used at retrieval is the *same client* as the loader (same model, same config).

### Retrieval — Designer / impact analysis

Structural calls (`impact_topdown`, `impact_bottomup`) follow the Nurture flow. Semantic discovery follows the BRO flow. No new flow shapes.

## Idempotency Model — Worked Example

Stable IDs:
- `urn:dm:kyc:CustomerProfile`
- `urn:svc:kyc:VerifyIdentity` (consumes `CustomerProfile`)
- `urn:svc:loyalty:RedeemPoints` (consumes `CustomerProfile`)

**Run 1 — first load:** all three IDs CREATE; LLM + embedding called for each; edges merged.

**Run 2 — same artifacts:** content hashes match → no-op. No LLM, no embedding, no writes.

**Run 3 — `CustomerProfile.description` changed:** hash miss → MERGE properties, re-summarize, re-embed. Edges untouched (consumers reference the same stable ID).

**Run 4 — `RedeemPoints` now consumes `CustomerProfileV2` instead:** hash miss → MERGE node; outgoing edge diff: DELETE old `→ CustomerProfile`, MERGE new `→ CustomerProfileV2`. `CustomerProfile` node NOT deleted (`VerifyIdentity` still consumes it).

**Run 5 — `--tombstone urn:dm:kyc:CustomerProfile`:** refuses with list of dependents (`VerifyIdentity`); succeeds only with `--force`.

### Invariants

- Stable ID is the only key. Names and descriptions can change; stable ID never does.
- Loader never deletes nodes implicitly. Removals are explicit tombstones.
- Edges are diffed per re-loaded source node. Adding/removing a consumer means re-loading the *consumer*, not the model.
- Hash gate prevents wasted LLM/embedding calls. Re-runs on unchanged content are free.

## Public API Summary

```python
from autobots_devtools_shared_lib.kg import (
    KGStore, KGReadStore, KGWriteStore, KGBatch, KGService,
    Node, Edge, Subgraph, Path, ScoredNode, NodeSummary,
    NodeFilter, RequirementDecomposition, DependentsExistError,
)
from autobots_devtools_shared_lib.kg.adapters.neo4j_store import Neo4jKGStore
from autobots_devtools_shared_lib.kg.embedding import Embedder
from autobots_devtools_shared_lib.kg.tools import (
    kg_get_subgraph, kg_get_dependencies, kg_get_node_summary,
    kg_semantic_search, kg_decompose_requirement,
    kg_impact_topdown, kg_impact_bottomup,
)
```

CLI: `kg-load --ids …` (neutral name; shared-lib entry point used by all consuming apps).

## Testing

**Port conformance suite** — `tests/contract/test_kgstore_conformance.py`. Parameterized over every `KGStore` implementation (today: `FakeKGStore`, `Neo4jKGStore`). Asserts the contract: upsert/get round-trip, traverse depth/direction/edge-type filters, `NodeFilter` semantics, `semantic_search` ranking, edge diffing, batch commit/rollback, `delete_node` raises `DependentsExistError`, etc. Adding a new adapter means making this suite pass — directly underwrites the engine-swap success criterion.

**Unit:**
- `KGService` — uses `FakeKGStore` (in-memory port impl in `tests/fakes/`): re-ranking, decompose orchestration, hydration shape, `model_version` mismatch handling.
- Loader components — `differ` (hash gate, edge-diff), `summarizer` (mock LLM), `embedder` (mock embedding), pipeline rollback on injected failure.
- Tools — given a `KGService`, each tool returns expected JSON shape (one test per tool, including `kg_get_node_summary`).

**Integration:**
- Loader end-to-end on a tiny fixture KG (3–5 artifacts) → real Neo4j → assert nodes/edges/embeddings present.
- Re-run loader with same fixtures → assert hash gate skips all LLM/embedding calls.
- Mutate one artifact's description → re-run → assert exactly one re-summarize + re-embed.

**Fixtures:** canonical mini-KG under `tests/fixtures/kg/`, covering all node types from the parallel-track schema.

Markers: `unit`, `integration`, `slow` (workspace convention).

## Boundary Rules

- Cypher (or any engine-specific query language) lives **only** in adapter files.
- `KGStore` returns plain dataclasses — no driver types escape.
- Tools call `KGService`; never the store directly.
- Loader writes via the write port; never bypasses to the adapter directly.
- **Read/write split is typed:** `KGService` is constructed with `KGReadStore` and cannot upcast to write methods. Only the loader receives a full `KGStore`. Enforced by pyright.
- All loader writes happen inside a `KGBatch` context manager; transactional rollback on any failure.
- **Filters are typed:** `NodeFilter` dataclass is the only filter shape crossing the port. Free-form `dict` filters are forbidden.
- `Embedder` is shared between loader and `KGService` via injection; both must use the same model. Stored embeddings carry `model_version`; mismatches are detected at runtime.
- Shared lib MUST NOT import from any consuming app package.

## Success Criteria

- Nurture can fetch the exact subgraph for a service named in an LLD via one tool call, deterministically, without LLM involvement.
- BRO can decompose a free-text business requirement into ranked candidate nodes across the entire portfolio in one tool call.
- Designer can run semantic discovery scoped to a node type and expand hits via the same structural primitive Nurture uses.
- Re-running the loader on unchanged artifacts is a true no-op (zero LLM calls, zero embedding calls, zero DB writes).
- Swapping Neo4j → Kuzu requires changes only in `kg/adapters/` and a constructor wiring change. No agent code, no service, no tool, no loader pipeline change.
- An MCP server can be added later as a purely additive entry point over the same `KGService` — no changes to layers below.

## Open Questions

- **Engine v1 confirmation.** Default Neo4j; revisit if Kuzu's embedded model is preferred for ops simplicity.
- **Embedding model choice.** Owned by `Embedder` config; pick at implementation time. Constraint: must support the dimensionality and batch throughput we need at ingestion time.
- **Summarizer prompts.** One per node type; drafted at implementation time once the parallel-track schema lands.
- **Ingestion trigger evolution.** Manual CLI in v1. Per-commit hooks or scheduled batch may follow if pilot demands it.
- **Error handling and observability.** Deferred per "happy path only" call; circle back before pilot promotion.
