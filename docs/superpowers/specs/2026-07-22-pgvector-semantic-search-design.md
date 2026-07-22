# pgvector Semantic Search — Design

**Date:** 2026-07-22
**Status:** Approved for planning
**Repo:** `autobots-devtools-shared-lib`

## Goal

A corpus-agnostic embedding + retrieval capability in shared-lib, following the
context-store idiom: Protocol-based store, pluggable implementations, factory
wiring, domain-injected DB layer. Any domain (KG nodes, KBE articles, Designer
sources) can index text chunks and run semantic search over them via a Python
API, a ready-made dynagent tool, or FastAPI routes.

## Scope

**In:** embedding generation, pgvector storage, similarity search, deletion,
collection registry, dimension-mismatch guard, agent tool, FastAPI router,
in-memory fake for tests.

**Out (YAGNI):** document loading and chunking (domains bring their own
chunks), hybrid keyword+vector search, re-ranking, per-collection embedding
dimensions, async SQLAlchemy migration.

## Architecture

```
domain code ─┐
agent tool ──┼─► SemanticSearchService ──► Embedder (Gemini first)
FastAPI ─────┘            │
                          └─────────────► VectorStore (Protocol)
                                            ├── PgVectorStore  (SQLAlchemy + pgvector)
                                            └── InMemoryVectorStore (tests)
```

New module: `common/services/vector/`.

### Embedder

Factory mirroring `dynagent/llm/llm.py`: `get_embedder()` resolves provider
from settings (`EmbeddingProvider` enum), returning a thin wrapper with
`embed_documents(texts) -> list[list[float]]` and `embed_query(text)`.

- Initial provider: Gemini `gemini-embedding-001` with
  `output_dimensionality=768` (Matryoshka truncation).
- Vectors are L2-normalized on write so cosine and inner product agree.
- Adding OpenAI/Bedrock later is a one-function change; callers never
  hardcode a provider.

### VectorStore Protocol

Storage + ANN math only — no embedding, no provider knowledge. Deals in
already-embedded docs and query vectors.

```python
@runtime_checkable
class VectorStore(Protocol):
    def upsert(self, collection: str, docs: Sequence[VectorDoc]) -> None: ...
    def search(
        self,
        collection: str,
        query_embedding: Sequence[float],
        *,
        top_k: int = 5,
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[ScoredDoc]: ...
    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        *,
        scope: str | None = None,
        version: str | None = None,
    ) -> None: ...
    def describe(self, collection: str) -> CollectionInfo | None: ...
```

Implementations:

- **`PgVectorStore`** — SQLAlchemy (sync, psycopg2, matching MER's
  `common/db/engine.py`) + `pgvector` package. Constructed with a
  domain-supplied sessionmaker; shared-lib never owns connection config.
  `upsert` = `INSERT … ON CONFLICT (collection, doc_id) DO UPDATE`;
  `search` = `ORDER BY embedding <=> :q LIMIT :k`.
- **`InMemoryVectorStore`** — brute-force cosine over a dict; satisfies the
  protocol for unit tests without Postgres (mirrors context store's
  `in_memory.py`).

### SemanticSearchService

The surface domains actually call. Pairs an `Embedder` with a `VectorStore`:

- `index(collection, chunks)` — hashes content, skips embedding for unchanged
  hashes, embeds the rest in batches, upserts.
- `search(collection, query, *, top_k, scope, version, kind, metadata_filter)`
  — embeds query, delegates, returns scored docs.
- `delete(...)` — passthrough.
- Enforces the dimension guard: before search/index, compares configured
  model+dim against the collection registry row via `describe()` and fails
  loudly on mismatch (`EmbeddingMismatchError`). First index into a new
  collection creates the registry row.

### Agent tool

`semantic_search` dynagent tool (`ToolRuntime[None, Dynagent]`) wrapping
`SemanticSearchService.search`. Shipped in shared-lib; domains opt in via
`register_usecase_tools`. Collection and default filters come from tool
config/state, query from the LLM.

### FastAPI router

`dynagent/api/` router (same precedent as `thread_store.py`) with:

- `POST /vector/{collection}/search` — query + optional scope/version/kind +
  metadata filter, returns scored docs.
- `POST /vector/{collection}/documents` — index chunks.
- `DELETE /vector/{collection}` — by ids or scope/version.
- `GET /vector/{collection}` — `describe()`.

Domains mount it and supply the service via dependency injection.

## Data model

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vector_collections (
    name        text PRIMARY KEY,          -- "kg-nodes", "kbe-articles"
    model       text NOT NULL,             -- "gemini-embedding-001"
    dim         smallint NOT NULL,         -- 768
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vector_documents (
    pk           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collection   text NOT NULL REFERENCES vector_collections(name)
                     ON DELETE CASCADE,
    doc_id       text NOT NULL,            -- caller-supplied, stable across re-index
    scope        text,                     -- component/repo, e.g. "fbp-product-deposit-app"
    version      text,                     -- "develop", "v1", "v1.1"
    kind         text,                     -- node/doc type, e.g. "Model--DTO", "LPU"
    content      text NOT NULL,            -- chunk text returned to callers
    content_hash text NOT NULL,            -- sha256; skip re-embedding unchanged chunks
    metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding    vector(768) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (collection, doc_id)
);

CREATE INDEX idx_vd_embedding  ON vector_documents USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_vd_scope      ON vector_documents (collection, scope, version, kind);
CREATE INDEX idx_vd_metadata   ON vector_documents USING gin (metadata jsonb_path_ops);
```

### Key decisions

- **Promoted filter columns (`scope`, `version`, `kind`).** The known corpora
  all share these axes (KG: component/branch/node-type; KBE:
  product/version/article-type; Designer: repo/iteration/source-type).
  First-class columns give real planner statistics (JSONB keys have none,
  which skews HNSW scan strategy), typo-proof typed filters, and lifecycle
  alignment: regenerating a KG snapshot is one indexed
  `DELETE WHERE collection/scope/version`. JSONB `metadata` remains for the
  corpus-specific long tail only.
- **One global dimension: 768.** pgvector's HNSW index caps at 2000 dims for
  the `vector` type, so Gemini's 3072 default is un-indexable anyway; 768 via
  Matryoshka truncation is the quality/cost sweet spot. Set in settings; all
  collections conform. Registry records dim per collection so a future
  second dimension has known escape hatches (partial cast indexes,
  `halfvec`) without building them now.
- **Cosine distance** (`vector_cosine_ops`, `<=>`), vectors normalized on
  write.
- **`(collection, doc_id)` unique + surrogate PK.** Callers keep stable ids
  (`"lld-4711#chunk-3"`); clean upserts; cheap bigint for index/FK.
- **`content_hash`** makes re-indexing idempotent — the embedding API call is
  the only per-token cost, skipped when content is unchanged.
- **Rejected:** encoding scope/version into collection names (kills
  cross-component search, explodes the registry); LangChain
  `langchain-postgres` PGVector (schema churn, weak migration story, filter
  DSL); table-per-collection dynamic DDL (runtime DDL, migration sprawl).

## KG use case mapping

One collection `kg-nodes`; per node file
(`fbp-product-deposit-app--develop--Model--DTO--Account.json`):

| Column | Value |
|---|---|
| `doc_id` | kgId / file stem |
| `scope` | `fbp-product-deposit-app` |
| `version` | `develop` |
| `kind` | `Model--DTO` |
| `content` | node name + description |
| `metadata` | glossary terms, file path, etc. |

Typical query: `search("kg-nodes", "deposit account closure rules",
scope="fbp-product-deposit-app", version="develop", kind="LPU")` — fully
indexed SQL, no JSONB in the hot path.

## Error handling

- `EmbeddingMismatchError` — configured model/dim ≠ collection registry row.
- `CollectionNotFoundError` — search/delete on unknown collection.
- Embedding API failures propagate with context (batch index reports which
  doc_ids failed; no partial-batch silent success).
- Filtered HNSW caveat: heavy filters + ANN index can under-return; pin
  pgvector ≥ 0.8 (iterative index scans) and document the behavior.

## Migration & deployment

- SQL migration creates extension + tables + indexes (idempotent
  `IF NOT EXISTS`). Requires a Postgres with the pgvector extension
  available (≥ 0.8).
- New settings: `embedding_provider`, `embedding_model`, `embedding_dim`
  (default 768), Gemini key reused from existing settings.
- New dependency: `pgvector` (Python); `langchain-google-genai` already
  available for Gemini.

## Testing

- **Unit:** `SemanticSearchService` against `InMemoryVectorStore` + fake
  embedder (deterministic vectors): index/search/delete, hash-skip
  behavior, dimension guard, filter combinations.
- **Integration** (marker `integration`, requires Postgres+pgvector):
  `PgVectorStore` round-trip, upsert conflict path, scope/version delete,
  metadata containment filter, HNSW query plan sanity.
- **Tool/router:** tool registered and callable with mocked service; router
  tests via FastAPI `TestClient`.
