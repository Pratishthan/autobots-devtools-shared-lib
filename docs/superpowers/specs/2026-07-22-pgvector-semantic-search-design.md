# pgvector Semantic Search — Design

**Date:** 2026-07-22 (revised 2026-07-23 after design review)
**Status:** Approved for planning
**Repo:** `autobots-devtools-shared-lib`

## Goal

A corpus-agnostic embedding + retrieval capability in shared-lib, following the
context-store idiom: Protocol-based store, pluggable implementations, factory
wiring, domain-injected DB layer. Any domain (KG nodes, KBE articles, Designer
sources) can index documents and run semantic search over them via a Python
API, a ready-made dynagent tool, or FastAPI routes.

## Scope

**In:** chunking, embedding generation, pgvector storage, similarity search,
deletion, pruning of stale documents/chunks, collection registry,
dimension-mismatch guard, agent tool, FastAPI router, in-memory fake for
tests.

**Out (YAGNI):** document loading (domains bring their own text), hybrid
keyword+vector search, re-ranking, result dedup/grouping by parent document
(callers regroup chunks themselves), per-collection embedding dimensions,
async SQLAlchemy migration.

## Architecture

```
domain code ─┐
agent tool ──┼─► SemanticSearchService ──► Chunker (token-based splitter)
FastAPI ─────┘            │
                          ├─────────────► Embedder (OpenAI first)
                          │
                          └─────────────► VectorStore (Protocol)
                                            ├── PgVectorStore  (SQLAlchemy + pgvector)
                                            └── InMemoryVectorStore (tests)
```

New module: `common/services/vector/`.

### Chunker

Lives inside `SemanticSearchService` — the store stays chunk-agnostic.
`index()` accepts whole documents; the chunker splits each document's content
into token-sized chunks before embedding.

- Default implementation: `RecursiveCharacterTextSplitter.from_tiktoken_encoder`
  (`langchain-text-splitters`), sized in tokens so output always respects the
  embedding model's 8191-token input cap.
- Settings: `chunk_size_tokens` (default 1000), `chunk_overlap_tokens`
  (default 150). Global, like `embedding_dim`.
- Content at or under `chunk_size_tokens` passes through as a single chunk —
  the common case for KG nodes, which therefore pay no fragmentation.
- The splitter is deterministic: unchanged content re-chunks to byte-identical
  chunks, which is what makes per-chunk hash-skip effective (see upsert).

### Embedder

Factory mirroring `dynagent/llm/llm.py`: `get_embedder()` resolves provider
from settings (`EmbeddingProvider` enum), returning a thin wrapper with
`embed_documents(texts) -> list[list[float]]` and `embed_query(text)`. The
wrapper exposes its `model` and `dim` so the service can enforce the
dimension guard.

- Initial provider: OpenAI `text-embedding-3-small`, native dimension 1536
  (fits under pgvector's 2000-dim HNSW cap; no truncation needed).
- OpenAI vectors arrive unit-normalized; the wrapper defensively
  L2-normalizes anyway so future providers behave identically and cosine and
  inner product agree.
- Batching: embed in batches (default 128 texts/request, setting
  `embedding_batch_size`); retry transient failures (429/5xx) with
  exponential backoff before propagating.
- Adding Gemini/Bedrock later is a one-function change; callers never
  hardcode a provider.

### VectorStore Protocol

Storage + ANN math only — no embedding, no chunking, no provider knowledge.

```python
@runtime_checkable
class VectorStore(Protocol):
    def upsert(self, collection: str, docs: Sequence[VectorDoc]) -> UpsertResult: ...
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
        parent_ids: Sequence[str] | None = None,
    ) -> None: ...
    def describe(self, collection: str) -> CollectionInfo | None: ...
    def drop_collection(self, collection: str) -> None: ...
```

- `VectorDoc` carries `parent_id`, `chunk_index`, `content`, `content_hash`,
  family axes (`scope`, `version`, `kind`), `metadata`, and an **optional**
  `embedding`. Its `doc_id` is derived: `"{parent_id}#{chunk_index}"`.
- **Two-phase upsert — hash-skip lives in the store.** `upsert` diffs
  `content_hash` server-side in one statement (VALUES join against existing
  rows). Rows whose hash is unchanged are left alone; docs that are new or
  changed but carry no embedding are **not written** — their ids come back in
  `UpsertResult.needs_embedding`. The service embeds only those and calls
  `upsert` again with vectors attached. Unchanged content costs zero
  embedding calls and zero row churn.
- `ScoredDoc.score` is **cosine similarity** (higher is better, range
  [-1, 1]). Both implementations conform, so unit tests against the fake
  predict Postgres ordering.
- `metadata_filter` is **top-level key containment only** (`@>` semantics —
  what `jsonb_path_ops` GIN accelerates). No ranges, no negation; both
  implementations enforce the same semantics.

Implementations:

- **`PgVectorStore`** — SQLAlchemy (sync, psycopg2, matching MER's
  `common/db/engine.py`) + `pgvector` package. Constructed with a
  domain-supplied sessionmaker; shared-lib never owns connection config.
  Write path = `INSERT … ON CONFLICT (collection, doc_id) DO UPDATE`
  (explicitly setting `updated_at = now()`);
  search = `ORDER BY embedding <=> :q LIMIT :k`.
- **`InMemoryVectorStore`** — brute-force cosine over a dict; satisfies the
  protocol for unit tests without Postgres (mirrors context store's
  `in_memory.py`).

### SemanticSearchService

The surface domains actually call. Wires `Chunker` + `Embedder` +
`VectorStore`:

- `index(collection, docs, *, prune=False)` — for each input document
  (`parent_id`, `content`, family axes, `metadata`): chunk, hash each chunk,
  phase-1 upsert, embed only `needs_embedding`, phase-2 upsert.
  - **Chunk-tail prune (always):** if a re-indexed document produced fewer
    chunks than before, delete rows with the same `parent_id` and
    `chunk_index >=` the new count. Stale trailing chunks are always wrong.
  - **Family prune (opt-in `prune=True`):** after upsert, delete rows in the
    batch's families whose `parent_id` was not in the batch. Makes
    "re-index a snapshot" one idempotent call — no delete-then-reindex, so
    hash-skip keeps working.
- `search(collection, query, *, top_k, scope, version, kind,
  metadata_filter)` — embeds query, delegates, returns scored chunks. Results
  carry `parent_id`/`chunk_index`; regrouping into documents is the caller's
  concern.
- `delete(...)` — passthrough (by ids, parent_ids, or scope/version).
- `drop_collection(collection)` — removes the registry row; families and
  documents cascade. This is the recovery path for an embedding-model
  switch: drop, reconfigure, re-index.
- **Dimension guard:** before search/index, compares configured model+dim
  against the collection registry row (cached per collection after first
  `describe()`) and raises `EmbeddingMismatchError` on mismatch. First index
  into a new collection creates the registry row with
  `ON CONFLICT DO NOTHING` + re-read, so concurrent first-indexers converge.

### Wiring

Module-level singleton mirroring the context store's `set_context_store()`:
domains construct the service at startup (injecting their sessionmaker) and
call `set_semantic_search_service(service)`; the agent tool and router
resolve it via `get_semantic_search_service()`.

### Agent tool

`semantic_search` dynagent tool (`ToolRuntime[None, Dynagent]`) wrapping
`SemanticSearchService.search`. Shipped in shared-lib; domains opt in via
`register_usecase_tools`. Collection and default filters come from tool
config/state, query from the LLM.

### FastAPI router

`dynagent/api/` router (same mount pattern as `thread_store.py`) with:

- `POST /vector/{collection}/search` — query + optional scope/version/kind +
  metadata filter, returns scored chunks.
- `POST /vector/{collection}/documents` — index documents (optional
  `prune` flag).
- `DELETE /vector/{collection}` — by ids, parent_ids, or scope/version;
  `?drop=true` drops the collection itself (registry row + cascade).
- `GET /vector/{collection}` — `describe()`.

Route handlers are plain `def` (not `async def`) so FastAPI runs them in its
threadpool — the sync DB and embedding calls must never block the event loop.
(This intentionally diverges from `thread_store.py`'s async Protocol; the
store is sync to match MER's DB layer.) Routes carry no auth of their own;
domains are responsible for gating them behind their own auth middleware
when mounting.

## Data model

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE vector_collections (
    name        text PRIMARY KEY,          -- "kg-nodes", "kbe-articles"
    model       text NOT NULL,             -- "text-embedding-3-small"
    dim         smallint NOT NULL,         -- 1536
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vector_document_family (
    id          int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collection  text NOT NULL REFERENCES vector_collections(name)
                    ON DELETE CASCADE,
    scope       text,                      -- component/repo, e.g. "fbp-product-deposit-app"
    version     text,                      -- "develop", "v1", "v1.1"
    kind        text,                      -- node/doc type, e.g. "Model--DTO", "LPU"
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (collection, scope, version, kind)
);

CREATE TABLE vector_documents (
    pk           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collection   text NOT NULL REFERENCES vector_collections(name)
                     ON DELETE CASCADE,
    family_id    int NOT NULL REFERENCES vector_document_family(id)
                     ON DELETE CASCADE,
    parent_id    text NOT NULL,            -- caller's document id, stable across re-index
    chunk_index  int NOT NULL,             -- 0-based position within parent
    doc_id       text NOT NULL,            -- "{parent_id}#{chunk_index}"
    content      text NOT NULL,            -- chunk text returned to callers
    content_hash text NOT NULL,            -- sha256 of chunk; drives hash-skip in upsert
    metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding    vector(1536) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (collection, doc_id)
);

CREATE INDEX idx_vd_embedding ON vector_documents USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_vd_family    ON vector_documents (collection, family_id);
CREATE INDEX idx_vd_parent    ON vector_documents (collection, family_id, parent_id);
CREATE INDEX idx_vd_metadata  ON vector_documents USING gin (metadata jsonb_path_ops);
```

Requires Postgres ≥ 15 (`UNIQUE NULLS NOT DISTINCT`) with pgvector ≥ 0.8.

### Key decisions

- **Family table for the filter axes (`scope`, `version`, `kind`).** The
  known corpora all share these axes (KG: component/branch/node-type; KBE:
  product/version/article-type; Designer: repo/iteration/source-type), and
  searches essentially always filter by `kind`, so all three belong in the
  family key. Search resolves filter values to family ids first, then the
  hot path is `WHERE family_id IN (...)` — integer equality, which filtered
  HNSW handles far better than three text predicates, with real planner
  statistics (JSONB keys have none). Lifecycle alignment: regenerating a KG
  snapshot deletes a handful of family rows and cascades. JSONB `metadata`
  remains for the corpus-specific long tail only.
- **Chunking is the service's job.** Domains hand over whole documents;
  the service owns splitting, so no caller can exceed the embedding model's
  input cap and every corpus gets identical, deterministic chunking. Rows
  are chunks; `parent_id` + `chunk_index` tie them back to the source
  document for pruning and regrouping.
- **One global dimension: 1536** — `text-embedding-3-small`'s native size,
  indexable as-is (HNSW caps at 2000 dims for the `vector` type). Set in
  settings; all collections conform. `embedding_dim` must match the deployed
  `vector(1536)` schema — changing it requires a migration, not just a
  settings change; the registry records dim per collection so a future
  second dimension has known escape hatches (partial cast indexes,
  `halfvec`) without building them now.
- **Cosine distance** (`vector_cosine_ops`, `<=>`), vectors normalized on
  write; scores surfaced as similarity (higher better).
- **`(collection, doc_id)` unique + surrogate PK.** `doc_id` is derived from
  `parent_id` + `chunk_index`, so callers keep one stable id per document;
  clean upserts; cheap bigint for index/FK.
- **Two-phase upsert with server-side hash diff** makes re-indexing
  idempotent end to end: unchanged chunks cost nothing (no embedding call,
  no write), shrunk documents lose their tail chunks automatically, and
  `prune=True` clears documents that vanished from the corpus.
- **Rejected:** encoding scope/version into collection names (kills
  cross-component search, explodes the registry); LangChain
  `langchain-postgres` PGVector (schema churn, weak migration story, filter
  DSL); table-per-collection dynamic DDL (runtime DDL, migration sprawl);
  caller-side chunking (pushes the token-cap failure mode onto every
  domain).

## KG use case mapping

One collection `kg-nodes`; per node file
(`fbp-product-deposit-app--develop--Model--DTO--Account.json`):

| Field | Value |
|---|---|
| `parent_id` | kgId / file stem |
| family `scope` | `fbp-product-deposit-app` |
| family `version` | `develop` |
| family `kind` | `Model--DTO` |
| `content` | node name + description (typically one chunk) |
| `metadata` | glossary terms, file path, etc. |

Typical query: `search("kg-nodes", "deposit account closure rules",
scope="fbp-product-deposit-app", version="develop", kind="LPU")` — resolves
to a family-id filter, fully indexed SQL, no JSONB in the hot path.
Snapshot refresh: `index(..., prune=True)` with the full node set.

## Error handling

- `EmbeddingMismatchError` — configured model/dim ≠ collection registry row.
  Recovery: `drop_collection()` + re-index (documented operator path).
- `CollectionNotFoundError` — search/delete on unknown collection.
- Embedding API failures: transient errors retried with backoff, then
  propagate with context (batch index reports which parent_ids failed; no
  partial-batch silent success).
- Filtered HNSW caveat: heavy filters + ANN index can under-return; pin
  pgvector ≥ 0.8 (iterative index scans) and document the behavior. Note
  `top_k` above `hnsw.ef_search` (default 40) silently truncates — document
  the relationship.

## Migration & deployment

- SQL migration creates extension + tables + indexes (idempotent
  `IF NOT EXISTS`). Shared-lib ships the SQL; each domain applies it through
  its own migration pipeline. Requires Postgres ≥ 15 with pgvector ≥ 0.8.
- New settings: `embedding_provider` (default `openai`), `embedding_model`
  (default `text-embedding-3-small`), `embedding_dim` (default 1536),
  `embedding_batch_size` (default 128), `chunk_size_tokens` (default 1000),
  `chunk_overlap_tokens` (default 150), and new `openai_api_key` in
  `DynagentSettings`.
- New dependencies: `pgvector` (Python), `langchain-openai`,
  `langchain-text-splitters` (`tiktoken` is already a transitive
  dependency).

## Testing

- **Unit:** `SemanticSearchService` against `InMemoryVectorStore` + fake
  embedder (deterministic vectors): index/search/delete, two-phase
  hash-skip (unchanged docs produce zero embed calls), chunker determinism
  and single-chunk passthrough, chunk-tail prune, family prune, dimension
  guard, filter combinations, metadata containment semantics.
- **Integration** (marker `integration`, requires Postgres ≥ 15 +
  pgvector): `PgVectorStore` round-trip, upsert conflict + hash-diff path,
  family resolution and cascade deletes, scope/version delete,
  `drop_collection` cascade, metadata containment filter, HNSW query plan
  sanity.
- **Tool/router:** tool registered and callable with mocked service; router
  tests via FastAPI `TestClient`, including the `prune` and `drop` flags.
