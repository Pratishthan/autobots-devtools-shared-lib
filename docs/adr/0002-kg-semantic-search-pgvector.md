# KG semantic search: pgvector entry points, Neo4j for expansion

Status: accepted

Semantic search over the FBP knowledge graphs (one KG per FBP service, all loaded into a single
Neo4j instance) is served by **pgvector on the existing Postgres**, not by Neo4j's native vector
index and not by a dedicated engine (Qdrant). Vector search finds entry-point nodes by
`node_kg_id`; Neo4j remains the sole source of truth for the graph, and all neighborhood expansion
happens there via pre-defined Cypher templates. Embeddings are computed locally with
sentence-transformers — no external embedding API.

## Considered options

Sizing context for all three: 10–100 FBP components at ~1.5–3K nodes each → ~10⁴–10⁵ embeddable
nodes. All three options handle that capacity; the differentiators are filtered search, sync
architecture, and ops burden.

| Dimension | 1. Neo4j native vector index — rejected | 2. Neo4j + pgvector — **chosen** | 3. Neo4j + Qdrant — rejected |
|---|---|---|---|
| Capacity at 10⁴–10⁵ vectors | Fine (comfortable to ~10⁶) | Fine (headroom to 10⁶–10⁷) | Fine (10⁷+; overkill) |
| Component/branch-filtered search | **Decisive con**: no pre-filtered ANN in Neo4j 5.x — `queryNodes` takes no predicate, so scoped queries over-fetch k×(component count) and post-filter; degrades linearly with component count, and scoped queries are the dominant pattern | Indexed pre-filtering in SQL: `component`, `branch`, `label` as real columns in the ANN query; recall unaffected by component count | Strongest: payload indexes, quantization, tuned filtered ANN |
| Sync / consistency | None needed — embeddings are node properties; a KG reload replaces node + vector atomically | Permanent two-store sync obligation (mitigated by rebuild-per-component; see Consequences) | Same two-store sync cost as pgvector |
| Tool-path complexity | One driver, one session; search + expansion can be a single Cypher | Two stores per search: pgvector returns `node_kg_id`s, Neo4j resolves the graph — two configs, two failure modes | Same round-trip as pgvector, plus a second query DSL (typed `Filter` models) instead of SQL |
| Hybrid (keyword + vector) | Manual fusion with a separate full-text index | Mature SQL-side tsvector fusion | Native dense/sparse/hybrid with server-side fusion — best available |
| New infra | None | `vector` extension on the Postgres MER already runs (`MER_DATABASE_URL`) — a migration, not a service | A third service to run, monitor, secure, back up — locally and in prod |
| LangChain / LangGraph ecosystem | n/a (plain driver suffices) | `langchain-postgres` `PGVectorStore` core-team maintained (adopt `PGVectorStore` only — legacy `PGVector` is deprecated churn); LangGraph Postgres checkpointer/`BaseStore` semantic search share the same database; debuggable with `psql` | `langchain-qdrant` most polished and API-stable partner package; no LangGraph checkpointer/store synergy |
| Index modeling | One index per (label, property): 8–10 label indexes or a shared `:Searchable` label hack | Embeddings independent of graph shape — re-embeds and model swaps never touch Neo4j; couples shared-lib to a Postgres schema in addition to Neo4j | Named vectors allow multiple embedding models side by side |
| Tuning knobs | Minimal (no quantization control, limited HNSW params) | Standard pgvector HNSW params | Richest (quantization, sharding, HNSW control) — only pays off ~2 orders of magnitude beyond the projected corpus |

## Consequences

- **Two-store sync is accepted, and made boring by construction**: Neo4j is the source of truth;
  the embed step reads nodes from Neo4j and rebuilds/upserts vector rows per component keyed by
  `node_kg_id`. Vectors are derived data — a full rebuild of any component's vectors must always
  be safe and cheap. Deletes/renames are handled by rebuild, not by incremental delete tracking.
- Every search tool call spans two stores: pgvector returns `node_kg_id`s, Neo4j resolves
  nodes/neighborhoods. The tool path carries two connection configs and two failure modes.
- Embedding model swaps or re-embeds touch only Postgres, never the KG.
- Hybrid (keyword + vector) retrieval, if needed, uses Postgres tsvector fusion; if that proves
  inadequate at scale, Qdrant is the designated re-evaluation point — revisit this ADR rather
  than bolting search onto Neo4j.
