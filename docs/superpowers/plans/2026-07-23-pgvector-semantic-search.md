# pgvector Semantic Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A corpus-agnostic embedding + retrieval capability in `autobots-devtools-shared-lib` — any domain can index whole documents and run semantic search over them through a Python API, a dynagent tool, or FastAPI routes.

**Architecture:** New module `common/services/vector/` following the context-store idiom: a `VectorStore` Protocol with two implementations (`PgVectorStore` over SQLAlchemy + pgvector, `InMemoryVectorStore` for tests), a `SemanticSearchService` that owns chunking + embedding + the dimension guard, and a module-level singleton (`set_semantic_search_service`) that the agent tool and router resolve through. The store is sync (matching MER's psycopg2 DB layer); the domain supplies the sessionmaker, so shared-lib never owns connection config.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (sync, psycopg2), pgvector, langchain-openai, langchain-text-splitters + tiktoken, FastAPI, pydantic-settings, pytest (`asyncio_mode = "auto"`), ruff, pyright.

**Source spec:** `docs/superpowers/specs/2026-07-22-pgvector-semantic-search-design.md` — read it before starting.

## Global Constraints

- All work happens inside the repo `autobots-devtools-shared-lib` (its own git repo — commit from **inside** it, never from the workspace root; pre-commit hooks run ruff + pyright + pytest + poetry check).
- Python 3.12+, ruff line-length 100, double quotes, pyright basic mode. Ruff rule sets in force: `E, W, F, I, B, C4, UP, ARG, SIM, S, TCH, PTH, RET, TRY, PERF, RUF`.
- Run commands from `autobots-devtools-shared-lib/` with the shared workspace venv: `source ../.venv/bin/activate` (or prefix with `../.venv/bin/`). There is **no** per-repo venv.
- Every new module starts with two `# ABOUTME:` comment lines, matching the house style in `dynagent/api/router.py`.
- Exact settings names and defaults: `embedding_provider` = `openai`, `embedding_model` = `text-embedding-3-small`, `embedding_dim` = `1536`, `embedding_batch_size` = `128`, `chunk_size_tokens` = `1000`, `chunk_overlap_tokens` = `150`, `openai_api_key` = `""`.
- Exact table names: `vector_collections`, `vector_document_family`, `vector_documents`. Exact collection example names: `kg-nodes`, `kbe-articles`.
- Scores surfaced everywhere are **cosine similarity** (higher is better, range `[-1, 1]`), never distance.
- `metadata_filter` semantics are **top-level key containment with scalar values only** (`@>` on `jsonb`). Filter values that are `dict` or `list` raise `ValueError` in both implementations, so the fake predicts Postgres exactly.
- Postgres ≥ 15 (`UNIQUE NULLS NOT DISTINCT`) with pgvector ≥ 0.8 (iterative index scans). State these floors in the SQL file and the README.
- Unit tests must never require Postgres, an OpenAI key, or network. Integration tests carry `@pytest.mark.integration` and skip when `VECTOR_TEST_DATABASE_URL` is unset.
- **Every commit runs the pre-commit hooks**, which re-run `ruff`, `pyright src` (whole tree, not just changed files), and `pytest tests/unit -q`. Each task's own lint/type-check step therefore duplicates work the commit will redo — that is intentional, so a failure surfaces while you still have context. A hook failure at commit time is not a new problem; fix it, do not `--no-verify` past it.
- `poetry-lock-check` also runs whenever `pyproject.toml` changes. Only Task 0 touches it, and Task 0 re-locks — no other task should modify dependencies.
- **If a task fails and you cannot fix it:** stop, leave the branch exactly as it is, and report which task and step failed with the actual command output. Do not revert earlier tasks' commits, do not skip ahead to a later task, and do not mark a step done that did not pass. Each task's commit is a clean checkpoint to resume from.

## Deviations from the spec (deliberate, carried through every task)

The spec's `VectorStore` Protocol sketch is incomplete for the behaviour the same
spec requires. Three additions, applied consistently:

1. **`ensure_collection(collection, *, model, dim) -> CollectionInfo`** — the spec's
   "first index creates the registry row with `ON CONFLICT DO NOTHING` + re-read"
   is SQL, so it belongs to the store, not the service.
2. **`delete(...) -> int`** (spec said `-> None`) and a new `min_chunk_index`
   parameter — the chunk-tail prune needs "same `parent_id`, `chunk_index >= n`",
   and `IndexResult` needs the row count.
3. **`prune_missing(collection, family, keep_parent_ids) -> int`** — the family
   prune needs *exact* family matching (`IS NOT DISTINCT FROM`), whereas
   `search`/`delete` treat `None` as a wildcard. Rather than overload one method
   with two null-semantics, exact matching is contained in its own method.

Also: `upsert` diffs hashes with a `SELECT ... WHERE doc_id = ANY(:ids)` followed by
an `INSERT ... ON CONFLICT` for the changed rows (two statements), not a single
VALUES-join with `RETURNING`. Reason: `executemany` + `RETURNING` is not reliably
row-returning under psycopg2/`text()`, and the two-statement form makes
`PgVectorStore` and `InMemoryVectorStore` byte-for-byte identical in semantics —
which is the property the whole unit-test strategy rests on.

## File Structure

| File | Responsibility |
|---|---|
| `src/autobots_devtools_shared_lib/common/services/vector/__init__.py` (create) | Public re-exports for the whole subsystem |
| `src/autobots_devtools_shared_lib/common/services/vector/models.py` (create) | `VectorDoc`, `ScoredDoc`, `UpsertResult`, `CollectionInfo`, `IndexDoc`, `IndexResult`, `Family`, `compute_content_hash` |
| `src/autobots_devtools_shared_lib/common/services/vector/errors.py` (create) | `VectorStoreError` + 3 subclasses |
| `src/autobots_devtools_shared_lib/common/services/vector/vector_math.py` (create) | `l2_normalize`, `cosine_similarity`, `matches_metadata` |
| `src/autobots_devtools_shared_lib/common/services/vector/chunker.py` (create) | `Chunker` Protocol + `TokenChunker` |
| `src/autobots_devtools_shared_lib/common/services/vector/embedder.py` (create) | `Embedder` Protocol, `EmbeddingProvider`, `OpenAIEmbedder`, `get_embedder()` |
| `src/autobots_devtools_shared_lib/common/services/vector/store.py` (create) | `VectorStore` Protocol |
| `src/autobots_devtools_shared_lib/common/services/vector/in_memory.py` (create) | `InMemoryVectorStore` |
| `src/autobots_devtools_shared_lib/common/services/vector/pg_store.py` (create) | `PgVectorStore` |
| `src/autobots_devtools_shared_lib/common/services/vector/service.py` (create) | `SemanticSearchService` |
| `src/autobots_devtools_shared_lib/common/services/vector/factory.py` (create) | `set_semantic_search_service` / `get_semantic_search_service` |
| `src/autobots_devtools_shared_lib/common/services/vector/schema.sql` (create) | Idempotent DDL shipped to domains |
| `src/autobots_devtools_shared_lib/common/services/vector/README.md` (create) | Operator + integrator docs |
| `src/autobots_devtools_shared_lib/common/tools/vector_tools.py` (create) | `make_semantic_search_tool()` dynagent tool factory |
| `src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py` (create) | `build_vector_router()` + `register_vector_exception_handlers()` |
| `src/autobots_devtools_shared_lib/dynagent/config/dynagent_settings.py` (modify) | 7 new settings fields |
| `src/autobots_devtools_shared_lib/common/services/__init__.py` (modify) | Re-export the vector public API |
| `pyproject.toml` (modify) | 4 new runtime deps, 1 new dev dep (Task 0); version bump (Task 12) |
| `poetry.lock` (regenerate) | Re-locked in Task 0; `poetry-lock-check` gates the commit |
| `CONTEXT.md` (modify) | Vector vocabulary section |
| `tests/unit/vector/__init__.py` (create) | Test package marker |
| `tests/unit/vector/conftest.py` (create) | `FakeEmbedder`, `FakeChunker` fixtures |
| `tests/unit/vector/test_models.py` (create) | Derived `doc_id`, hashing |
| `tests/unit/vector/test_vector_math.py` (create) | Normalization, cosine, metadata containment |
| `tests/unit/vector/test_chunker.py` (create) | Determinism, single-chunk passthrough, empty |
| `tests/unit/vector/test_embedder.py` (create) | Batching, retry/backoff, dim guard, factory |
| `tests/unit/vector/test_in_memory_store.py` (create) | Full Protocol conformance |
| `tests/unit/vector/test_service.py` (create) | Two-phase hash-skip, prunes, dimension guard, filters |
| `tests/unit/vector/test_factory.py` (create) | Singleton set/get |
| `tests/unit/vector/test_vector_tools.py` (create) | Tool schema + invocation against a stub service |
| `tests/unit/vector/test_router.py` (create) | `TestClient` coverage incl. `prune` and `drop` |
| `tests/unit/test_dynagent_settings.py` (modify) | New settings defaults |
| `tests/integration/test_pgvector_store.py` (create) | Real Postgres round-trip |

---

### Task 0: Branch, dependencies, settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/autobots_devtools_shared_lib/dynagent/config/dynagent_settings.py`
- Test: `tests/unit/test_dynagent_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DynagentSettings.embedding_provider: str`, `.embedding_model: str`, `.embedding_dim: int`, `.embedding_batch_size: int`, `.chunk_size_tokens: int`, `.chunk_overlap_tokens: int`, `.openai_api_key: str`. Every later task reads these via `get_dynagent_settings()`.

Note `embedding_provider` is typed `str` here, **not** the `EmbeddingProvider` enum — the enum lives in `common/services/vector/embedder.py` (Task 3) and `dynagent_settings.py` must not import from the vector package (it would create a settings → vector → settings cycle). `get_embedder()` does the `EmbeddingProvider(...)` coercion, exactly as `lm()` does for a provider string.

- [ ] **Step 1: Create the feature branch**

```bash
cd /Users/pralhad/work/src/ws-autobots/autobots-devtools-shared-lib
git checkout -b feat/pgvector-semantic-search
```

- [ ] **Step 2: Add the dependencies**

In `pyproject.toml`, inside the `[project]` `dependencies = [...]` list, add these four entries after the existing `"tiktoken>=0.7.0",` line:

```toml
    "sqlalchemy>=2.0.0,<3.0.0",
    "pgvector>=0.3.6,<1.0.0",
    "langchain-openai>=1.1.0,<2.0.0",
    "langchain-text-splitters>=0.3.0,<2.0.0",
```

In the same file, inside the `dev = [...]` list, add one entry after `"pytest-xdist>=3.0.0",`:

```toml
    "psycopg2-binary>=2.9.9",
```

`sqlalchemy` was previously only a transitive dependency; `pg_store.py` imports it directly, so it must be declared. `tiktoken` is already declared and is what `langchain-text-splitters` uses for token-sized splitting.

- [ ] **Step 3: Re-lock and install**

`poetry.toml` sets `virtualenvs.create = false`, so `poetry install` installs
into the active shared workspace venv — this is what `make install-dev` does. Do
**not** reach around poetry with `pip install`: it would install the packages but
leave `poetry.lock` untouched, and the `poetry-lock-check` pre-commit hook fires
on any `pyproject.toml` change. An out-of-sync lock fails the commit in Step 9.

```bash
cd /Users/pralhad/work/src/ws-autobots/autobots-devtools-shared-lib
source ../.venv/bin/activate
poetry lock
poetry install
```

Expected: `poetry lock` resolves and rewrites `poetry.lock`; `poetry install`
completes without error.

- [ ] **Step 4: Verify the lock is in sync and the imports resolve**

```bash
poetry check --lock
../.venv/bin/python -c "
from pgvector.sqlalchemy import Vector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
import sqlalchemy; print('ok', sqlalchemy.__version__)
"
```

Expected: `poetry check --lock` exits 0 (a `[project.license]` deprecation
warning is pre-existing and harmless), then `ok 2.0.x` with no ImportError.

- [ ] **Step 5: Write the failing settings test**

Append to `tests/unit/test_dynagent_settings.py`:

```python
def test_embedding_and_chunking_defaults():
    from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings

    settings = DynagentSettings(_env_file=None)

    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_dim == 1536
    assert settings.embedding_batch_size == 128
    assert settings.chunk_size_tokens == 1000
    assert settings.chunk_overlap_tokens == 150
    assert settings.openai_api_key == ""


def test_embedding_settings_read_from_env(monkeypatch):
    from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import DynagentSettings

    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("EMBEDDING_DIM", "3072")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    settings = DynagentSettings(_env_file=None)

    assert settings.embedding_model == "text-embedding-3-large"
    assert settings.embedding_dim == 3072
    assert settings.openai_api_key == "sk-test"
```

- [ ] **Step 6: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/test_dynagent_settings.py -k embedding -v --no-cov
```

Expected: FAIL — `ValidationError` / `AttributeError` for the unknown `embedding_provider` field.

- [ ] **Step 7: Add the settings fields**

In `src/autobots_devtools_shared_lib/dynagent/config/dynagent_settings.py`, insert this block immediately after the `anthropic_api_key` field and before the `# Workspace settings` comment:

```python
    openai_api_key: str = Field(
        default="", description="OpenAI API key for embeddings (env: OPENAI_API_KEY)"
    )

    # Embedding settings (env: EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIM,
    # EMBEDDING_BATCH_SIZE). Typed as str, not the EmbeddingProvider enum, so this
    # module stays free of any import from common.services.vector; get_embedder()
    # coerces the string, mirroring how lm() coerces a provider string.
    embedding_provider: str = Field(
        default="openai", description="Embedding provider identifier"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small", description="Embedding model name"
    )
    embedding_dim: int = Field(
        default=1536,
        description="Embedding vector dimension; must match the deployed vector(N) column",
    )
    embedding_batch_size: int = Field(
        default=128, description="Texts per embedding API request"
    )

    # Chunking settings (env: CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
    chunk_size_tokens: int = Field(
        default=1000, description="Maximum tokens per indexed chunk"
    )
    chunk_overlap_tokens: int = Field(
        default=150, description="Token overlap between consecutive chunks"
    )
```

- [ ] **Step 8: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/test_dynagent_settings.py -v --no-cov
```

Expected: PASS, including the pre-existing tests in that file.

- [ ] **Step 9: Commit**

`poetry.lock` must be staged alongside `pyproject.toml` — the `poetry-lock-check`
hook fails the commit otherwise.

```bash
git add pyproject.toml poetry.lock src/autobots_devtools_shared_lib/dynagent/config/dynagent_settings.py tests/unit/test_dynagent_settings.py
git commit -m "feat(vector): add embedding/chunking settings and pgvector dependencies"
```

---

### Task 1: Value types, errors, and vector math

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Create: `src/autobots_devtools_shared_lib/common/services/vector/models.py`
- Create: `src/autobots_devtools_shared_lib/common/services/vector/errors.py`
- Create: `src/autobots_devtools_shared_lib/common/services/vector/vector_math.py`
- Create: `tests/unit/vector/__init__.py`
- Test: `tests/unit/vector/test_models.py`
- Test: `tests/unit/vector/test_vector_math.py`

**Interfaces:**
- Consumes: nothing.
- Produces — every later task imports these exact names from
  `autobots_devtools_shared_lib.common.services.vector`:
  - `Family(NamedTuple)` with fields `scope: str | None`, `version: str | None`, `kind: str | None` (all default `None`).
  - `VectorDoc` frozen dataclass: `parent_id: str`, `chunk_index: int`, `content: str`, `content_hash: str`, `scope: str | None = None`, `version: str | None = None`, `kind: str | None = None`, `metadata: Mapping[str, Any] = {}`, `embedding: Sequence[float] | None = None`; properties `doc_id -> str` (`f"{parent_id}#{chunk_index}"`) and `family -> Family`.
  - `ScoredDoc` frozen dataclass: `doc_id: str`, `parent_id: str`, `chunk_index: int`, `content: str`, `score: float`, `scope`, `version`, `kind`, `metadata`.
  - `UpsertResult` frozen dataclass: `written: tuple[str, ...]`, `skipped: tuple[str, ...]`, `needs_embedding: tuple[str, ...]`.
  - `CollectionInfo` frozen dataclass: `name: str`, `model: str`, `dim: int`, `document_count: int`.
  - `IndexDoc` frozen dataclass: `parent_id: str`, `content: str`, `scope`, `version`, `kind`, `metadata`.
  - `IndexResult` frozen dataclass: `chunks_written: int`, `chunks_skipped: int`, `chunks_pruned: int`, `documents_pruned: int`.
  - `compute_content_hash(text: str) -> str` (sha256 hex).
  - `l2_normalize(vector: Sequence[float]) -> list[float]`, `cosine_similarity(a, b) -> float`, `matches_metadata(row_metadata, metadata_filter) -> bool`.
  - Errors: `VectorStoreError(RuntimeError)`, `CollectionNotFoundError`, `EmbeddingMismatchError`, `EmbeddingProviderError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/__init__.py` (empty file), then create `tests/unit/vector/test_models.py`:

```python
# ABOUTME: Unit tests for the vector value types.
# ABOUTME: Covers derived doc_id, family projection, and content hashing.

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    Family,
    VectorDoc,
    compute_content_hash,
)


def test_doc_id_is_derived_from_parent_and_chunk_index():
    doc = VectorDoc(
        parent_id="Account", chunk_index=3, content="body", content_hash="abc"
    )

    assert doc.doc_id == "Account#3"


def test_family_projects_the_three_axes():
    doc = VectorDoc(
        parent_id="Account",
        chunk_index=0,
        content="body",
        content_hash="abc",
        scope="fbp-product-deposit-app",
        version="develop",
        kind="Model--DTO",
    )

    assert doc.family == Family("fbp-product-deposit-app", "develop", "Model--DTO")


def test_family_defaults_to_all_none():
    doc = VectorDoc(parent_id="a", chunk_index=0, content="b", content_hash="c")

    assert doc.family == Family(None, None, None)


def test_content_hash_is_stable_and_content_sensitive():
    assert compute_content_hash("hello") == compute_content_hash("hello")
    assert compute_content_hash("hello") != compute_content_hash("hello ")
    assert len(compute_content_hash("hello")) == 64


def test_vector_doc_is_immutable():
    doc = VectorDoc(parent_id="a", chunk_index=0, content="b", content_hash="c")

    with pytest.raises(AttributeError):
        doc.content = "changed"  # type: ignore[misc]
```

Create `tests/unit/vector/test_vector_math.py`:

```python
# ABOUTME: Unit tests for vector normalization, cosine similarity, and metadata containment.
# ABOUTME: These semantics must hold identically in InMemoryVectorStore and PgVectorStore.

import math

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    cosine_similarity,
    l2_normalize,
    matches_metadata,
)


def test_l2_normalize_produces_unit_length():
    normalized = l2_normalize([3.0, 4.0])

    assert normalized == pytest.approx([0.6, 0.8])
    assert math.isclose(sum(v * v for v in normalized), 1.0)


def test_l2_normalize_leaves_zero_vector_untouched():
    assert l2_normalize([0.0, 0.0]) == [0.0, 0.0]


def test_cosine_similarity_of_identical_vectors_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_ignores_magnitude():
    assert cosine_similarity([1.0, 0.0], [7.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_with_zero_vector_is_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_metadata_containment_matches_subset_of_top_level_keys():
    row = {"path": "a/b.json", "terms": ["deposit"], "active": True}

    assert matches_metadata(row, {"path": "a/b.json"}) is True
    assert matches_metadata(row, {"active": True}) is True
    assert matches_metadata(row, {"path": "a/b.json", "active": True}) is True
    assert matches_metadata(row, {"path": "other.json"}) is False
    assert matches_metadata(row, {"missing": 1}) is False


def test_metadata_containment_with_empty_or_none_filter_matches_everything():
    assert matches_metadata({"a": 1}, None) is True
    assert matches_metadata({"a": 1}, {}) is True


def test_metadata_containment_rejects_non_scalar_filter_values():
    with pytest.raises(ValueError, match="scalar"):
        matches_metadata({"terms": ["deposit"]}, {"terms": ["deposit"]})

    with pytest.raises(ValueError, match="scalar"):
        matches_metadata({"nested": {"a": 1}}, {"nested": {"a": 1}})
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector -v --no-cov
```

Expected: FAIL — `ModuleNotFoundError: No module named 'autobots_devtools_shared_lib.common.services.vector'`.

- [ ] **Step 3: Write `errors.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/errors.py`:

```python
# ABOUTME: Error types for the vector search subsystem.
# ABOUTME: All inherit VectorStoreError so callers can catch the whole family.


class VectorStoreError(RuntimeError):
    """Base class for every vector-search failure."""


class CollectionNotFoundError(VectorStoreError):
    """Raised when a collection has no registry row.

    Search and delete never create collections implicitly; only indexing does.
    """


class EmbeddingMismatchError(VectorStoreError):
    """Raised when the configured embedding model/dimension differs from the collection's.

    Recovery is drop_collection() followed by a full re-index; vectors from two
    different models are not comparable, so there is no in-place migration.
    """


class EmbeddingProviderError(VectorStoreError):
    """Raised when the embedding provider fails or returns an unusable response."""
```

- [ ] **Step 4: Write `models.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/models.py`:

```python
# ABOUTME: Immutable value types exchanged between the service, the stores, and callers.
# ABOUTME: VectorDoc is a chunk row; IndexDoc is a whole source document.

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence  # noqa: TC003
from dataclasses import dataclass, field
from typing import Any, NamedTuple


class Family(NamedTuple):
    """The three filter axes a document belongs to.

    All three are part of the family key, so `(None, "develop", None)` is a
    different family from `("app", "develop", None)`.
    """

    scope: str | None = None
    version: str | None = None
    kind: str | None = None


@dataclass(frozen=True, slots=True)
class VectorDoc:
    """One chunk, ready to be written to a store.

    `embedding` is None on the first (diff) phase of an upsert and populated on
    the second; the store never embeds anything itself.
    """

    parent_id: str
    chunk_index: int
    content: str
    content_hash: str
    scope: str | None = None
    version: str | None = None
    kind: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    embedding: Sequence[float] | None = None

    @property
    def doc_id(self) -> str:
        """Stable per-chunk identity, derived so callers only track parent ids."""
        return f"{self.parent_id}#{self.chunk_index}"

    @property
    def family(self) -> Family:
        return Family(self.scope, self.version, self.kind)


@dataclass(frozen=True, slots=True)
class ScoredDoc:
    """One search hit. `score` is cosine similarity — higher is better."""

    doc_id: str
    parent_id: str
    chunk_index: int
    content: str
    score: float
    scope: str | None = None
    version: str | None = None
    kind: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Outcome of one upsert phase, partitioned by what the store did with each doc."""

    written: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    needs_embedding: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    """Registry row for a collection plus its current chunk count."""

    name: str
    model: str
    dim: int
    document_count: int


@dataclass(frozen=True, slots=True)
class IndexDoc:
    """A whole source document handed to SemanticSearchService.index().

    The service chunks it; callers never chunk.
    """

    parent_id: str
    content: str
    scope: str | None = None
    version: str | None = None
    kind: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def family(self) -> Family:
        return Family(self.scope, self.version, self.kind)


@dataclass(frozen=True, slots=True)
class IndexResult:
    """What one index() call changed."""

    chunks_written: int = 0
    chunks_skipped: int = 0
    chunks_pruned: int = 0
    documents_pruned: int = 0


def compute_content_hash(text: str) -> str:
    """Return the sha256 hex digest of `text`, used to skip unchanged chunks."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Write `vector_math.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/vector_math.py`:

```python
# ABOUTME: Pure helpers shared by the embedder and the in-memory store.
# ABOUTME: matches_metadata mirrors Postgres jsonb @> containment exactly.

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_SCALAR_TYPES = (str, int, float, bool, type(None))


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return `vector` scaled to unit length; a zero vector is returned unchanged.

    Normalizing on write means cosine similarity and inner product agree, so a
    future provider that returns unnormalized vectors behaves like OpenAI's.
    """
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return list(vector)
    return [v / norm for v in vector]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return cosine similarity in [-1, 1]; 0.0 when either vector is all zeros."""
    norm_a = math.sqrt(sum(v * v for v in a))
    norm_b = math.sqrt(sum(v * v for v in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def matches_metadata(
    row_metadata: Mapping[str, Any], metadata_filter: Mapping[str, Any] | None
) -> bool:
    """Return True when every filter key is present in `row_metadata` with an equal value.

    Scalar-only by design: this is what `jsonb @>` accelerated by a
    `jsonb_path_ops` GIN index does for scalar values, and restricting to scalars
    is what keeps this fake's answer identical to Postgres'. A dict or list value
    would mean recursive sub-containment in Postgres and plain equality here, so
    it is rejected instead of silently diverging.
    """
    if not metadata_filter:
        return True
    for key, value in metadata_filter.items():
        if not isinstance(value, _SCALAR_TYPES):
            msg = (
                f"metadata_filter value for {key!r} must be a scalar "
                f"(str, int, float, bool, None), got {type(value).__name__}"
            )
            raise ValueError(msg)
        if key not in row_metadata or row_metadata[key] != value:
            return False
    return True
```

- [ ] **Step 6: Write the package `__init__.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`. This is the file every later task extends — start with only what exists now:

```python
"""Corpus-agnostic embedding and semantic search.

Public surface for domains:
  from autobots_devtools_shared_lib.common.services.vector import (
      SemanticSearchService, IndexDoc, get_semantic_search_service,
  )
"""

from autobots_devtools_shared_lib.common.services.vector.errors import (
    CollectionNotFoundError,
    EmbeddingMismatchError,
    EmbeddingProviderError,
    VectorStoreError,
)
from autobots_devtools_shared_lib.common.services.vector.models import (
    CollectionInfo,
    Family,
    IndexDoc,
    IndexResult,
    ScoredDoc,
    UpsertResult,
    VectorDoc,
    compute_content_hash,
)
from autobots_devtools_shared_lib.common.services.vector.vector_math import (
    cosine_similarity,
    l2_normalize,
    matches_metadata,
)

__all__ = [
    "CollectionInfo",
    "CollectionNotFoundError",
    "EmbeddingMismatchError",
    "EmbeddingProviderError",
    "Family",
    "IndexDoc",
    "IndexResult",
    "ScoredDoc",
    "UpsertResult",
    "VectorDoc",
    "VectorStoreError",
    "compute_content_hash",
    "cosine_similarity",
    "l2_normalize",
    "matches_metadata",
]
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector -v --no-cov
```

Expected: PASS, 18 tests.

- [ ] **Step 8: Lint and type-check**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
```

Expected: no ruff findings, `0 errors` from pyright.

- [ ] **Step 9: Commit**

```bash
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): value types, errors, and vector math helpers"
```

---

### Task 2: Chunker

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/chunker.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/unit/vector/test_chunker.py`

**Interfaces:**
- Consumes: `get_dynagent_settings()` (Task 0).
- Produces:
  - `Chunker` Protocol with one method `split(self, content: str) -> list[str]`.
  - `TokenChunker(*, chunk_size_tokens: int | None = None, chunk_overlap_tokens: int | None = None, encoding_name: str = "cl100k_base")` implementing it. `None` arguments fall back to settings.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/test_chunker.py`:

```python
# ABOUTME: Unit tests for TokenChunker.
# ABOUTME: Determinism and single-chunk passthrough are what make hash-skip effective.

from autobots_devtools_shared_lib.common.services.vector import Chunker, TokenChunker


def test_token_chunker_satisfies_the_protocol():
    assert isinstance(TokenChunker(), Chunker)


def test_short_content_passes_through_as_one_chunk():
    chunker = TokenChunker(chunk_size_tokens=1000, chunk_overlap_tokens=150)

    chunks = chunker.split("Account holds the customer's deposit balance.")

    assert chunks == ["Account holds the customer's deposit balance."]


def test_chunking_is_deterministic():
    chunker = TokenChunker(chunk_size_tokens=20, chunk_overlap_tokens=5)
    content = " ".join(f"sentence number {i} about deposits." for i in range(60))

    first = chunker.split(content)
    second = TokenChunker(chunk_size_tokens=20, chunk_overlap_tokens=5).split(content)

    assert len(first) > 1
    assert first == second


def test_long_content_is_split_and_every_chunk_respects_the_token_cap():
    import tiktoken

    encoding = tiktoken.get_encoding("cl100k_base")
    chunker = TokenChunker(chunk_size_tokens=20, chunk_overlap_tokens=0)
    content = " ".join(f"token{i}" for i in range(400))

    chunks = chunker.split(content)

    assert len(chunks) > 1
    assert all(len(encoding.encode(chunk)) <= 20 for chunk in chunks)


def test_empty_and_whitespace_content_produce_no_chunks():
    chunker = TokenChunker()

    assert chunker.split("") == []
    assert chunker.split("   \n\t ") == []


def test_defaults_come_from_settings(monkeypatch):
    monkeypatch.setenv("CHUNK_SIZE_TOKENS", "25")
    monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "0")
    from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
        DynagentSettings,
        set_dynagent_settings,
    )

    set_dynagent_settings(DynagentSettings(_env_file=None))
    try:
        chunker = TokenChunker()
        assert chunker.chunk_size_tokens == 25
        assert chunker.chunk_overlap_tokens == 0
    finally:
        set_dynagent_settings(DynagentSettings(_env_file=None))
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_chunker.py -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'Chunker'`.

- [ ] **Step 3: Write `chunker.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/chunker.py`:

```python
# ABOUTME: Token-sized document splitting, owned by the service so no caller can
# ABOUTME: exceed the embedding model's input cap and every corpus chunks identically.

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    get_dynagent_settings,
)

if TYPE_CHECKING:
    from langchain_text_splitters import RecursiveCharacterTextSplitter


@runtime_checkable
class Chunker(Protocol):
    """Splits a document's text into embeddable pieces."""

    def split(self, content: str) -> list[str]:  # pragma: no cover - Protocol
        """Return the ordered chunks of `content`; empty list for blank input."""
        ...


class TokenChunker:
    """RecursiveCharacterTextSplitter sized in tokens, not characters.

    Sizing in tokens is what guarantees output respects the embedding model's
    8191-token input cap. The splitter is deterministic, so unchanged content
    re-chunks to byte-identical chunks — the property per-chunk hash-skip needs.
    Content at or under `chunk_size_tokens` comes back as a single chunk, so the
    common case (a KG node) pays no fragmentation.
    """

    def __init__(
        self,
        *,
        chunk_size_tokens: int | None = None,
        chunk_overlap_tokens: int | None = None,
        encoding_name: str = "cl100k_base",
    ) -> None:
        settings = get_dynagent_settings()
        self.chunk_size_tokens = (
            chunk_size_tokens if chunk_size_tokens is not None else settings.chunk_size_tokens
        )
        self.chunk_overlap_tokens = (
            chunk_overlap_tokens
            if chunk_overlap_tokens is not None
            else settings.chunk_overlap_tokens
        )
        self.encoding_name = encoding_name
        self._splitter: RecursiveCharacterTextSplitter | None = None

    def _get_splitter(self) -> RecursiveCharacterTextSplitter:
        """Build the splitter on first use; it loads a tiktoken encoding from disk."""
        if self._splitter is None:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name=self.encoding_name,
                chunk_size=self.chunk_size_tokens,
                chunk_overlap=self.chunk_overlap_tokens,
            )
        return self._splitter

    def split(self, content: str) -> list[str]:
        text = content.strip()
        if not text:
            return []
        return self._get_splitter().split_text(text)
```

- [ ] **Step 4: Export the new names**

In `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`, add the import block (keep imports alphabetically ordered by module — this goes above the `errors` import):

```python
from autobots_devtools_shared_lib.common.services.vector.chunker import Chunker, TokenChunker
```

and add `"Chunker",` and `"TokenChunker",` to `__all__` in sorted position.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector/test_chunker.py -v --no-cov
```

Expected: PASS, 6 tests.

- [ ] **Step 6: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): token-sized deterministic chunker"
```

---

### Task 3: Embedder and provider factory

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/embedder.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/unit/vector/test_embedder.py`

**Interfaces:**
- Consumes: `l2_normalize` and `EmbeddingProviderError` (Task 1); `get_dynagent_settings()` (Task 0).
- Produces:
  - `EmbeddingProvider(StrEnum)` with one member `OPENAI = "openai"`.
  - `Embedder` Protocol — attributes `model: str`, `dim: int`; methods `embed_documents(self, texts: Sequence[str]) -> list[list[float]]` and `embed_query(self, text: str) -> list[float]`. **Not** `@runtime_checkable`: a Protocol with non-method members raises `TypeError` under `isinstance`.
  - `OpenAIEmbedder(*, model=None, dim=None, api_key=None, batch_size=None, max_retries=4, base_delay=0.5, sleep=time.sleep, client=None)` implementing it.
  - `get_embedder(provider: str | None = None, model: str | None = None, dim: int | None = None) -> Embedder`.

The `client` and `sleep` constructor arguments are the seams the tests use — no network, no monkeypatching of module globals.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/test_embedder.py`:

```python
# ABOUTME: Unit tests for OpenAIEmbedder and get_embedder, with a stub client.
# ABOUTME: Covers batching, L2 normalization, transient retry/backoff, and the dim guard.

import math

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    EmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbedder,
    get_embedder,
)


class StubClient:
    """Stands in for langchain_openai.OpenAIEmbeddings."""

    def __init__(self, dim=4, failures=0, exc=None):
        self.dim = dim
        self.failures = failures
        self.exc = exc or _transient_error()
        self.batches: list[list[str]] = []
        self.queries: list[str] = []

    def embed_documents(self, texts):
        if self.failures > 0:
            self.failures -= 1
            raise self.exc
        self.batches.append(list(texts))
        return [[float(len(t))] * self.dim for t in texts]

    def embed_query(self, text):
        if self.failures > 0:
            self.failures -= 1
            raise self.exc
        self.queries.append(text)
        return [float(len(text))] * self.dim


class _Err(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def _transient_error():
    return _Err(429)


def _make(client, **kwargs):
    kwargs.setdefault("model", "text-embedding-3-small")
    kwargs.setdefault("dim", 4)
    kwargs.setdefault("sleep", lambda _seconds: None)
    return OpenAIEmbedder(client=client, **kwargs)


def test_embed_documents_returns_unit_vectors():
    embedder = _make(StubClient())

    vectors = embedder.embed_documents(["abcd"])

    assert len(vectors) == 1
    assert math.isclose(sum(v * v for v in vectors[0]), 1.0)


def test_embed_documents_splits_into_batches():
    client = StubClient()
    embedder = _make(client, batch_size=2)

    vectors = embedder.embed_documents(["a", "bb", "ccc", "dddd", "eeeee"])

    assert len(vectors) == 5
    assert client.batches == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]


def test_embed_documents_with_no_texts_makes_no_calls():
    client = StubClient()
    embedder = _make(client)

    assert embedder.embed_documents([]) == []
    assert client.batches == []


def test_embed_query_returns_a_unit_vector():
    embedder = _make(StubClient())

    vector = embedder.embed_query("deposit account closure")

    assert math.isclose(sum(v * v for v in vector), 1.0)


def test_transient_failures_are_retried_with_backoff():
    client = StubClient(failures=2)
    delays: list[float] = []
    embedder = _make(client, sleep=delays.append)

    vectors = embedder.embed_documents(["abcd"])

    assert len(vectors) == 1
    assert delays == [0.5, 1.0]


def test_transient_failures_propagate_after_max_retries():
    client = StubClient(failures=99)
    embedder = _make(client, max_retries=2)

    with pytest.raises(EmbeddingProviderError, match="after 2 retries"):
        embedder.embed_documents(["abcd"])


def test_non_transient_failures_are_not_retried():
    client = StubClient(failures=99, exc=_Err(401))
    delays: list[float] = []
    embedder = _make(client, sleep=delays.append)

    with pytest.raises(EmbeddingProviderError):
        embedder.embed_documents(["abcd"])

    assert delays == []


def test_wrong_dimension_from_provider_is_rejected():
    embedder = _make(StubClient(dim=8), dim=4)

    with pytest.raises(EmbeddingProviderError, match="expected 4"):
        embedder.embed_documents(["abcd"])


def test_get_embedder_uses_settings(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("EMBEDDING_DIM", "1536")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
        DynagentSettings,
        set_dynagent_settings,
    )

    set_dynagent_settings(DynagentSettings(_env_file=None))
    try:
        embedder = get_embedder()
        assert embedder.model == "text-embedding-3-small"
        assert embedder.dim == 1536
    finally:
        set_dynagent_settings(DynagentSettings(_env_file=None))


def test_get_embedder_rejects_an_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        get_embedder(provider="cohere")


def test_embedding_provider_enum_values():
    assert EmbeddingProvider.OPENAI == "openai"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_embedder.py -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'EmbeddingProvider'`.

- [ ] **Step 3: Write `embedder.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/embedder.py`:

```python
# ABOUTME: Embedding provider factory mirroring dynagent/llm/llm.py.
# ABOUTME: Wrappers normalize vectors and retry transient provider failures.

from __future__ import annotations

import time
from collections.abc import Callable, Sequence  # noqa: TC003
from enum import StrEnum
from typing import Any, Protocol

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.services.vector.errors import EmbeddingProviderError
from autobots_devtools_shared_lib.common.services.vector.vector_math import l2_normalize
from autobots_devtools_shared_lib.dynagent.config.dynagent_settings import (
    get_dynagent_settings,
)

logger = get_logger(__name__)

_TRANSIENT_STATUS_CODES = frozenset({408, 409, 429})


class EmbeddingProvider(StrEnum):
    """Supported embedding providers."""

    OPENAI = "openai"


class Embedder(Protocol):
    """Turns text into vectors.

    Deliberately not @runtime_checkable: a Protocol carrying non-method members
    (`model`, `dim`) raises TypeError under isinstance().
    """

    model: str
    dim: int

    def embed_documents(
        self, texts: Sequence[str]
    ) -> list[list[float]]:  # pragma: no cover - Protocol
        """Embed indexable texts, preserving input order."""
        ...

    def embed_query(self, text: str) -> list[float]:  # pragma: no cover - Protocol
        """Embed a single search query."""
        ...


def _is_transient(exc: Exception) -> bool:
    """True for rate limits and server-side errors, which are worth retrying."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "http_status", None)
    if not isinstance(status, int):
        return False
    return status in _TRANSIENT_STATUS_CODES or status >= 500


class OpenAIEmbedder:
    """OpenAI embeddings with batching, backoff, and defensive normalization.

    OpenAI already returns unit vectors; normalizing anyway means a future
    provider that does not behaves identically, and cosine and inner product
    stay interchangeable.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        dim: int | None = None,
        api_key: str | None = None,
        batch_size: int | None = None,
        max_retries: int = 4,
        base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        client: Any | None = None,
    ) -> None:
        settings = get_dynagent_settings()
        self.model = model if model is not None else settings.embedding_model
        self.dim = dim if dim is not None else settings.embedding_dim
        self._batch_size = (
            batch_size if batch_size is not None else settings.embedding_batch_size
        )
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._sleep = sleep
        self._client = client
        self._api_key = api_key if api_key is not None else settings.openai_api_key

    def _get_client(self) -> Any:
        """Construct the langchain client on first use so importing is key-free."""
        if self._client is None:
            from langchain_openai import OpenAIEmbeddings

            self._client = OpenAIEmbeddings(model=self.model, api_key=self._api_key or None)
        return self._client

    def _call(self, operation: Callable[[], Any], *, what: str) -> Any:
        """Run `operation`, retrying transient failures with exponential backoff."""
        attempt = 0
        while True:
            try:
                return operation()
            except Exception as exc:
                if not _is_transient(exc) or attempt >= self._max_retries:
                    msg = (
                        f"Embedding {what} failed after {attempt} retries "
                        f"using model {self.model}: {exc!s}"
                    )
                    raise EmbeddingProviderError(msg) from exc
                delay = self._base_delay * (2**attempt)
                logger.warning(
                    "Transient embedding failure (%s), retrying in %.1fs: %s", what, delay, exc
                )
                self._sleep(delay)
                attempt += 1

    def _check_dim(self, vector: list[float]) -> list[float]:
        if len(vector) != self.dim:
            msg = (
                f"Embedding model {self.model} returned {len(vector)} dimensions, "
                f"expected {self.dim}; check the embedding_dim setting."
            )
            raise EmbeddingProviderError(msg)
        return l2_normalize(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        client = self._get_client()
        out: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            vectors = self._call(
                lambda batch=batch: client.embed_documents(batch), what="embed_documents"
            )
            out.extend(self._check_dim(list(vector)) for vector in vectors)
        return out

    def embed_query(self, text: str) -> list[float]:
        client = self._get_client()
        vector = self._call(lambda: client.embed_query(text), what="embed_query")
        return self._check_dim(list(vector))


def get_embedder(
    provider: str | None = None, model: str | None = None, dim: int | None = None
) -> Embedder:
    """Return an Embedder; each argument defaults to the configured settings value."""
    settings = get_dynagent_settings()
    raw_provider = provider if provider is not None else settings.embedding_provider
    try:
        resolved = EmbeddingProvider(raw_provider)
    except ValueError:
        msg = f"Unsupported embedding provider: {raw_provider}"
        raise ValueError(msg) from None

    if resolved == EmbeddingProvider.OPENAI:
        return OpenAIEmbedder(model=model, dim=dim)
    msg = f"Unsupported embedding provider: {resolved}"  # pragma: no cover - defensive
    raise ValueError(msg)  # pragma: no cover - defensive
```

- [ ] **Step 4: Export the new names**

In `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`, add:

```python
from autobots_devtools_shared_lib.common.services.vector.embedder import (
    Embedder,
    EmbeddingProvider,
    OpenAIEmbedder,
    get_embedder,
)
```

and add `"Embedder"`, `"EmbeddingProvider"`, `"OpenAIEmbedder"`, `"get_embedder"` to `__all__` in sorted position.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector/test_embedder.py -v --no-cov
```

Expected: PASS, 11 tests.

- [ ] **Step 6: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): embedder protocol, OpenAI wrapper, and provider factory"
```

---

### Task 4: VectorStore Protocol and InMemoryVectorStore

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/store.py`
- Create: `src/autobots_devtools_shared_lib/common/services/vector/in_memory.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/unit/vector/test_in_memory_store.py`

**Interfaces:**
- Consumes: `VectorDoc`, `ScoredDoc`, `UpsertResult`, `CollectionInfo`, `Family` (Task 1); `cosine_similarity`, `matches_metadata` (Task 1); `CollectionNotFoundError` (Task 1).
- Produces: `VectorStore` Protocol (`@runtime_checkable` — methods only) and `InMemoryVectorStore()` implementing it. Exact signatures, which Tasks 5 and 8 both depend on:

```python
def ensure_collection(self, collection: str, *, model: str, dim: int) -> CollectionInfo: ...
def describe(self, collection: str) -> CollectionInfo | None: ...
def drop_collection(self, collection: str) -> None: ...
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
    kind: str | None = None,
    parent_ids: Sequence[str] | None = None,
    min_chunk_index: int | None = None,
) -> int: ...
def prune_missing(
    self, collection: str, family: Family, keep_parent_ids: Sequence[str]
) -> int: ...
```

**The three semantic rules both implementations must obey — the whole test strategy rests on these:**

1. **Upsert partition.** For each doc, in order: (a) an existing row with the same `content_hash` → `skipped`, whatever the doc's embedding; (b) otherwise `doc.embedding is None` → `needs_embedding`, **not written**; (c) otherwise → `written`.
2. **Filter nulls.** In `search` and `delete`, a `None` axis means *no constraint*. In `prune_missing`, the `Family` is matched *exactly* — `Family(None, "develop", None)` matches only rows whose scope and kind are actually NULL.
3. **Delete safety.** `delete` with no criterion at all raises `ValueError`; it never wipes a collection by accident. Use `drop_collection` for that.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/test_in_memory_store.py`:

```python
# ABOUTME: Conformance tests for InMemoryVectorStore.
# ABOUTME: Every behaviour asserted here must hold identically for PgVectorStore.

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    CollectionNotFoundError,
    Family,
    InMemoryVectorStore,
    VectorDoc,
    VectorStore,
    compute_content_hash,
)

COLLECTION = "kg-nodes"


def make_doc(parent_id, chunk_index=0, content="body", embedding=None, **axes):
    return VectorDoc(
        parent_id=parent_id,
        chunk_index=chunk_index,
        content=content,
        content_hash=compute_content_hash(content),
        embedding=embedding,
        **axes,
    )


@pytest.fixture
def store():
    store = InMemoryVectorStore()
    store.ensure_collection(COLLECTION, model="fake-embedding", dim=2)
    return store


def test_satisfies_the_protocol():
    assert isinstance(InMemoryVectorStore(), VectorStore)


def test_ensure_collection_is_idempotent_and_keeps_the_first_registration(store):
    again = store.ensure_collection(COLLECTION, model="other-model", dim=99)

    assert again.model == "fake-embedding"
    assert again.dim == 2
    assert again.name == COLLECTION


def test_describe_returns_none_for_an_unknown_collection(store):
    assert store.describe("nope") is None


def test_describe_counts_chunk_rows(store):
    store.upsert(COLLECTION, [make_doc("a", embedding=[1.0, 0.0])])
    store.upsert(COLLECTION, [make_doc("a", chunk_index=1, content="x", embedding=[0.0, 1.0])])

    info = store.describe(COLLECTION)

    assert info is not None
    assert info.document_count == 2


def test_upsert_on_an_unknown_collection_raises(store):
    with pytest.raises(CollectionNotFoundError):
        store.upsert("nope", [make_doc("a", embedding=[1.0, 0.0])])


def test_upsert_without_embeddings_reports_needs_embedding_and_writes_nothing(store):
    result = store.upsert(COLLECTION, [make_doc("a"), make_doc("b")])

    assert result.needs_embedding == ("a#0", "b#0")
    assert result.written == ()
    assert result.skipped == ()
    assert store.describe(COLLECTION).document_count == 0


def test_upsert_with_embeddings_writes(store):
    result = store.upsert(COLLECTION, [make_doc("a", embedding=[1.0, 0.0])])

    assert result.written == ("a#0",)
    assert store.describe(COLLECTION).document_count == 1


def test_upsert_skips_rows_whose_hash_is_unchanged(store):
    store.upsert(COLLECTION, [make_doc("a", content="same", embedding=[1.0, 0.0])])

    diff = store.upsert(COLLECTION, [make_doc("a", content="same")])

    assert diff.skipped == ("a#0",)
    assert diff.needs_embedding == ()


def test_upsert_reports_changed_content_as_needing_embedding(store):
    store.upsert(COLLECTION, [make_doc("a", content="old", embedding=[1.0, 0.0])])

    diff = store.upsert(COLLECTION, [make_doc("a", content="new")])

    assert diff.needs_embedding == ("a#0",)


def test_upsert_overwrites_content_and_embedding_on_change(store):
    store.upsert(COLLECTION, [make_doc("a", content="old", embedding=[1.0, 0.0])])
    store.upsert(COLLECTION, [make_doc("a", content="new", embedding=[0.0, 1.0])])

    hits = store.search(COLLECTION, [0.0, 1.0], top_k=5)

    assert [(h.doc_id, h.content) for h in hits] == [("a#0", "new")]
    assert store.describe(COLLECTION).document_count == 1


def test_search_returns_cosine_similarity_ordered_high_to_low(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("near", embedding=[1.0, 0.0]),
            make_doc("mid", embedding=[1.0, 1.0]),
            make_doc("far", embedding=[0.0, 1.0]),
        ],
    )

    hits = store.search(COLLECTION, [1.0, 0.0], top_k=3)

    assert [h.parent_id for h in hits] == ["near", "mid", "far"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[2].score == pytest.approx(0.0)


def test_search_respects_top_k(store):
    store.upsert(
        COLLECTION,
        [make_doc(f"d{i}", embedding=[1.0, float(i)]) for i in range(5)],
    )

    assert len(store.search(COLLECTION, [1.0, 0.0], top_k=2)) == 2


def test_search_on_an_unknown_collection_raises(store):
    with pytest.raises(CollectionNotFoundError):
        store.search("nope", [1.0, 0.0])


def test_search_filters_by_family_axes(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", embedding=[1.0, 0.0], scope="app", version="develop", kind="LPU"),
            make_doc("b", embedding=[1.0, 0.0], scope="app", version="develop", kind="Model--DTO"),
            make_doc("c", embedding=[1.0, 0.0], scope="other", version="develop", kind="LPU"),
        ],
    )

    assert [h.parent_id for h in store.search(COLLECTION, [1.0, 0.0], kind="LPU")] == ["a", "c"]
    assert [h.parent_id for h in store.search(COLLECTION, [1.0, 0.0], scope="app")] == ["a", "b"]
    assert [
        h.parent_id
        for h in store.search(COLLECTION, [1.0, 0.0], scope="app", version="develop", kind="LPU")
    ] == ["a"]


def test_search_without_filters_returns_every_family(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", embedding=[1.0, 0.0], scope="app"),
            make_doc("b", embedding=[1.0, 0.0], scope="other"),
        ],
    )

    assert len(store.search(COLLECTION, [1.0, 0.0], top_k=10)) == 2


def test_search_filters_by_metadata_containment(store):
    store.upsert(
        COLLECTION,
        [
            VectorDoc(
                parent_id="a",
                chunk_index=0,
                content="x",
                content_hash="h1",
                metadata={"path": "a.json", "tier": 1},
                embedding=[1.0, 0.0],
            ),
            VectorDoc(
                parent_id="b",
                chunk_index=0,
                content="y",
                content_hash="h2",
                metadata={"path": "b.json", "tier": 2},
                embedding=[1.0, 0.0],
            ),
        ],
    )

    hits = store.search(COLLECTION, [1.0, 0.0], metadata_filter={"tier": 1})

    assert [h.parent_id for h in hits] == ["a"]
    assert hits[0].metadata["path"] == "a.json"


def test_search_rejects_a_non_scalar_metadata_filter_value(store):
    store.upsert(COLLECTION, [make_doc("a", embedding=[1.0, 0.0])])

    with pytest.raises(ValueError, match="scalar"):
        store.search(COLLECTION, [1.0, 0.0], metadata_filter={"terms": ["x"]})


def test_search_returns_the_family_axes_on_each_hit(store):
    store.upsert(
        COLLECTION,
        [make_doc("a", embedding=[1.0, 0.0], scope="app", version="develop", kind="LPU")],
    )

    hit = store.search(COLLECTION, [1.0, 0.0])[0]

    assert (hit.scope, hit.version, hit.kind) == ("app", "develop", "LPU")
    assert (hit.parent_id, hit.chunk_index, hit.doc_id) == ("a", 0, "a#0")


def test_delete_by_ids(store):
    store.upsert(
        COLLECTION,
        [make_doc("a", embedding=[1.0, 0.0]), make_doc("b", embedding=[1.0, 0.0])],
    )

    assert store.delete(COLLECTION, ids=["a#0"]) == 1
    assert [h.parent_id for h in store.search(COLLECTION, [1.0, 0.0])] == ["b"]


def test_delete_by_parent_ids_removes_every_chunk(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", chunk_index=0, content="c0", embedding=[1.0, 0.0]),
            make_doc("a", chunk_index=1, content="c1", embedding=[1.0, 0.0]),
            make_doc("b", embedding=[1.0, 0.0]),
        ],
    )

    assert store.delete(COLLECTION, parent_ids=["a"]) == 2
    assert store.describe(COLLECTION).document_count == 1


def test_delete_with_min_chunk_index_removes_only_the_tail(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", chunk_index=i, content=f"c{i}", embedding=[1.0, 0.0])
            for i in range(4)
        ],
    )

    assert store.delete(COLLECTION, parent_ids=["a"], min_chunk_index=2) == 2
    assert sorted(h.chunk_index for h in store.search(COLLECTION, [1.0, 0.0], top_k=10)) == [0, 1]


def test_delete_by_scope_and_version(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", embedding=[1.0, 0.0], scope="app", version="v1"),
            make_doc("b", embedding=[1.0, 0.0], scope="app", version="v2"),
        ],
    )

    assert store.delete(COLLECTION, scope="app", version="v1") == 1
    assert [h.parent_id for h in store.search(COLLECTION, [1.0, 0.0])] == ["b"]


def test_delete_ands_every_supplied_criterion(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", embedding=[1.0, 0.0], scope="app"),
            make_doc("b", embedding=[1.0, 0.0], scope="other"),
        ],
    )

    assert store.delete(COLLECTION, parent_ids=["a", "b"], scope="app") == 1


def test_delete_without_any_criterion_raises(store):
    with pytest.raises(ValueError, match="at least one"):
        store.delete(COLLECTION)


def test_delete_on_an_unknown_collection_raises(store):
    with pytest.raises(CollectionNotFoundError):
        store.delete("nope", ids=["a#0"])


def test_prune_missing_removes_only_absent_parents_in_the_exact_family(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("keep", embedding=[1.0, 0.0], scope="app", version="develop", kind="LPU"),
            make_doc("gone", embedding=[1.0, 0.0], scope="app", version="develop", kind="LPU"),
            make_doc("other", embedding=[1.0, 0.0], scope="app", version="develop", kind="DTO"),
        ],
    )

    removed = store.prune_missing(COLLECTION, Family("app", "develop", "LPU"), ["keep"])

    assert removed == 1
    assert sorted(h.parent_id for h in store.search(COLLECTION, [1.0, 0.0], top_k=10)) == [
        "keep",
        "other",
    ]


def test_prune_missing_matches_null_axes_exactly(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("nulls", embedding=[1.0, 0.0]),
            make_doc("scoped", embedding=[1.0, 0.0], scope="app"),
        ],
    )

    removed = store.prune_missing(COLLECTION, Family(None, None, None), [])

    assert removed == 1
    assert [h.parent_id for h in store.search(COLLECTION, [1.0, 0.0], top_k=10)] == ["scoped"]


def test_prune_missing_with_an_empty_family_is_a_no_op(store):
    store.upsert(COLLECTION, [make_doc("a", embedding=[1.0, 0.0], scope="app")])

    assert store.prune_missing(COLLECTION, Family("absent", None, None), ["x"]) == 0


def test_drop_collection_removes_the_registry_row_and_every_document(store):
    store.upsert(COLLECTION, [make_doc("a", embedding=[1.0, 0.0])])

    store.drop_collection(COLLECTION)

    assert store.describe(COLLECTION) is None
    with pytest.raises(CollectionNotFoundError):
        store.search(COLLECTION, [1.0, 0.0])


def test_drop_collection_is_idempotent(store):
    store.drop_collection(COLLECTION)
    store.drop_collection(COLLECTION)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_in_memory_store.py -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'InMemoryVectorStore'`.

- [ ] **Step 3: Write `store.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/store.py`:

```python
# ABOUTME: The VectorStore Protocol — storage and ANN math only.
# ABOUTME: No embedding, no chunking, no provider knowledge lives behind this seam.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from autobots_devtools_shared_lib.common.services.vector.models import (
        CollectionInfo,
        Family,
        ScoredDoc,
        UpsertResult,
        VectorDoc,
    )


@runtime_checkable
class VectorStore(Protocol):
    """Persistence and similarity search for pre-embedded chunks.

    Null semantics differ by method on purpose: `search` and `delete` treat a
    None axis as "no constraint", while `prune_missing` matches a Family
    exactly, NULLs included.
    """

    def ensure_collection(
        self, collection: str, *, model: str, dim: int
    ) -> CollectionInfo:  # pragma: no cover - Protocol
        """Create the registry row if absent and return the effective row.

        Concurrent first-indexers converge: the loser of the race reads the
        winner's row rather than overwriting it.
        """
        ...

    def describe(
        self, collection: str
    ) -> CollectionInfo | None:  # pragma: no cover - Protocol
        """Return the registry row plus chunk count, or None if unregistered."""
        ...

    def drop_collection(self, collection: str) -> None:  # pragma: no cover - Protocol
        """Remove the collection and cascade its families and documents. Idempotent."""
        ...

    def upsert(
        self, collection: str, docs: Sequence[VectorDoc]
    ) -> UpsertResult:  # pragma: no cover - Protocol
        """Diff by content_hash and write only what changed.

        Docs whose hash matches an existing row are skipped; docs that are new
        or changed but carry no embedding are returned in `needs_embedding` and
        NOT written. Callers embed those and call again.
        """
        ...

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
    ) -> list[ScoredDoc]:  # pragma: no cover - Protocol
        """Return the `top_k` nearest chunks by cosine similarity, highest first."""
        ...

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        *,
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        parent_ids: Sequence[str] | None = None,
        min_chunk_index: int | None = None,
    ) -> int:  # pragma: no cover - Protocol
        """Delete rows matching every supplied criterion; return the row count.

        Raises ValueError when no criterion is given — use drop_collection to
        empty a collection.
        """
        ...

    def prune_missing(
        self, collection: str, family: Family, keep_parent_ids: Sequence[str]
    ) -> int:  # pragma: no cover - Protocol
        """Delete rows in the exact `family` whose parent_id is not in `keep_parent_ids`."""
        ...
```

- [ ] **Step 4: Write `in_memory.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/in_memory.py`:

```python
# ABOUTME: Brute-force VectorStore over dicts, for unit tests without Postgres.
# ABOUTME: Semantics are identical to PgVectorStore so tests here predict production.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from autobots_devtools_shared_lib.common.services.vector.errors import CollectionNotFoundError
from autobots_devtools_shared_lib.common.services.vector.models import (
    CollectionInfo,
    Family,
    ScoredDoc,
    UpsertResult,
)
from autobots_devtools_shared_lib.common.services.vector.vector_math import (
    cosine_similarity,
    matches_metadata,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from autobots_devtools_shared_lib.common.services.vector.models import VectorDoc


@dataclass(slots=True)
class _Row:
    doc_id: str
    parent_id: str
    chunk_index: int
    content: str
    content_hash: str
    scope: str | None
    version: str | None
    kind: str | None
    metadata: dict[str, Any]
    embedding: list[float]

    @property
    def family(self) -> Family:
        return Family(self.scope, self.version, self.kind)


@dataclass(slots=True)
class _Collection:
    model: str
    dim: int
    rows: dict[str, _Row] = field(default_factory=dict)


class InMemoryVectorStore:
    """In-process VectorStore. Not safe across processes; test and dev use only."""

    def __init__(self) -> None:
        self._collections: dict[str, _Collection] = {}

    def _require(self, collection: str) -> _Collection:
        entry = self._collections.get(collection)
        if entry is None:
            raise CollectionNotFoundError(collection)
        return entry

    def ensure_collection(self, collection: str, *, model: str, dim: int) -> CollectionInfo:
        if collection not in self._collections:
            self._collections[collection] = _Collection(model=model, dim=dim)
        entry = self._collections[collection]
        return CollectionInfo(
            name=collection, model=entry.model, dim=entry.dim, document_count=len(entry.rows)
        )

    def describe(self, collection: str) -> CollectionInfo | None:
        entry = self._collections.get(collection)
        if entry is None:
            return None
        return CollectionInfo(
            name=collection, model=entry.model, dim=entry.dim, document_count=len(entry.rows)
        )

    def drop_collection(self, collection: str) -> None:
        self._collections.pop(collection, None)

    def upsert(self, collection: str, docs: Sequence[VectorDoc]) -> UpsertResult:
        entry = self._require(collection)
        written: list[str] = []
        skipped: list[str] = []
        needs: list[str] = []

        for doc in docs:
            existing = entry.rows.get(doc.doc_id)
            if existing is not None and existing.content_hash == doc.content_hash:
                skipped.append(doc.doc_id)
                continue
            if doc.embedding is None:
                needs.append(doc.doc_id)
                continue
            entry.rows[doc.doc_id] = _Row(
                doc_id=doc.doc_id,
                parent_id=doc.parent_id,
                chunk_index=doc.chunk_index,
                content=doc.content,
                content_hash=doc.content_hash,
                scope=doc.scope,
                version=doc.version,
                kind=doc.kind,
                metadata=dict(doc.metadata),
                embedding=list(doc.embedding),
            )
            written.append(doc.doc_id)

        return UpsertResult(tuple(written), tuple(skipped), tuple(needs))

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
    ) -> list[ScoredDoc]:
        entry = self._require(collection)
        hits: list[ScoredDoc] = []
        for row in entry.rows.values():
            if not _axes_match(row, scope=scope, version=version, kind=kind):
                continue
            if not matches_metadata(row.metadata, metadata_filter):
                continue
            hits.append(
                ScoredDoc(
                    doc_id=row.doc_id,
                    parent_id=row.parent_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    score=cosine_similarity(query_embedding, row.embedding),
                    scope=row.scope,
                    version=row.version,
                    kind=row.kind,
                    metadata=dict(row.metadata),
                )
            )
        # doc_id breaks score ties so ordering is reproducible across runs.
        hits.sort(key=lambda hit: (-hit.score, hit.doc_id))
        return hits[:top_k]

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        *,
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        parent_ids: Sequence[str] | None = None,
        min_chunk_index: int | None = None,
    ) -> int:
        entry = self._require(collection)
        criteria = (ids, scope, version, kind, parent_ids, min_chunk_index)
        if all(criterion is None for criterion in criteria):
            msg = (
                "delete() requires at least one criterion "
                "(ids, parent_ids, scope, version, kind, min_chunk_index); "
                "use drop_collection() to empty a collection."
            )
            raise ValueError(msg)

        id_set = set(ids) if ids is not None else None
        parent_set = set(parent_ids) if parent_ids is not None else None

        doomed = [
            row.doc_id
            for row in entry.rows.values()
            if (id_set is None or row.doc_id in id_set)
            and (parent_set is None or row.parent_id in parent_set)
            and (min_chunk_index is None or row.chunk_index >= min_chunk_index)
            and _axes_match(row, scope=scope, version=version, kind=kind)
        ]
        for doc_id in doomed:
            del entry.rows[doc_id]
        return len(doomed)

    def prune_missing(
        self, collection: str, family: Family, keep_parent_ids: Sequence[str]
    ) -> int:
        entry = self._require(collection)
        keep = set(keep_parent_ids)
        doomed = [
            row.doc_id
            for row in entry.rows.values()
            if row.family == family and row.parent_id not in keep
        ]
        for doc_id in doomed:
            del entry.rows[doc_id]
        return len(doomed)


def _axes_match(
    row: _Row, *, scope: str | None, version: str | None, kind: str | None
) -> bool:
    """Wildcard axis matching: a None filter constrains nothing."""
    if scope is not None and row.scope != scope:
        return False
    if version is not None and row.version != version:
        return False
    return not (kind is not None and row.kind != kind)
```

- [ ] **Step 5: Export the new names**

In `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`, add:

```python
from autobots_devtools_shared_lib.common.services.vector.in_memory import InMemoryVectorStore
from autobots_devtools_shared_lib.common.services.vector.store import VectorStore
```

and add `"InMemoryVectorStore"` and `"VectorStore"` to `__all__` in sorted position.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector/test_in_memory_store.py -v --no-cov
```

Expected: PASS, 28 tests.

- [ ] **Step 7: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): VectorStore protocol and in-memory implementation"
```

---

### Task 5: SemanticSearchService

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/service.py`
- Create: `tests/unit/vector/conftest.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/unit/vector/test_service.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces:

```python
class SemanticSearchService:
    def __init__(
        self,
        store: VectorStore,
        *,
        embedder: Embedder | None = None,
        chunker: Chunker | None = None,
    ) -> None: ...

    def index(
        self, collection: str, docs: Sequence[IndexDoc], *, prune: bool = False
    ) -> IndexResult: ...

    def search(
        self,
        collection: str,
        query: str,
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
        kind: str | None = None,
        parent_ids: Sequence[str] | None = None,
    ) -> int: ...

    def describe(self, collection: str) -> CollectionInfo | None: ...
    def drop_collection(self, collection: str) -> None: ...
```

  Tasks 9 (tool) and 10 (router) call exactly these.

**Algorithm for `index`, in order — implement it in this order and nothing else:**

1. Verify/create the collection (dimension guard).
2. For every `IndexDoc`: chunk, hash each chunk, build `VectorDoc`s. Record the chunk count per `parent_id` and the parent ids per `Family`.
3. Phase-1 `upsert` with no embeddings → partition.
4. Embed only `needs_embedding`, in one `embed_documents` call; phase-2 `upsert` with vectors attached.
5. **Chunk-tail prune (always):** group parent ids by their new chunk count, then one `delete(parent_ids=..., min_chunk_index=count)` per distinct count. Grouping matters — a 5 000-node snapshot where nearly every document is one chunk costs one or two statements, not 5 000.
6. **Family prune (only when `prune=True`):** one `prune_missing` per family in the batch.

- [ ] **Step 1: Write the test fixtures**

Note on the `store` fixture below: Task 4's `tests/unit/vector/test_in_memory_store.py`
already defines its own local `store` fixture, which pre-registers the collection.
A fixture defined in a test module wins over a same-named one in `conftest.py`, so
that file keeps its own and is unaffected by this one. Leave both as they are —
do not "unify" them, the two tasks want different starting states.

Create `tests/unit/vector/conftest.py`:

```python
# ABOUTME: Deterministic fakes for the vector unit tests — no network, no Postgres.
# ABOUTME: FakeEmbedder scores by keyword overlap so relevance assertions are predictable.

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    InMemoryVectorStore,
    SemanticSearchService,
    l2_normalize,
)

VOCAB = ("deposit", "account", "closure", "invoice", "payment", "user", "report", "audit")


class FakeEmbedder:
    """Bag-of-words embedder over a fixed vocabulary.

    Text sharing vocabulary words with the query scores higher, so ordering
    assertions mean something. Text with no vocabulary hit maps to the uniform
    vector, which is equidistant from everything.
    """

    model = "fake-embedding"
    dim = len(VOCAB)

    def __init__(self) -> None:
        self.document_batches: list[list[str]] = []
        self.queries: list[str] = []

    @property
    def embed_calls(self) -> int:
        return len(self.document_batches)

    @property
    def embedded_texts(self) -> list[str]:
        return [text for batch in self.document_batches for text in batch]

    def embed_documents(self, texts):
        self.document_batches.append(list(texts))
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        self.queries.append(text)
        return self._vector(text)

    def _vector(self, text):
        lowered = text.lower()
        raw = [float(lowered.count(word)) for word in VOCAB]
        if not any(raw):
            raw = [1.0] * len(VOCAB)
        return l2_normalize(raw)


class FixedChunker:
    """Splits on a marker so chunk counts are exact and obvious in tests."""

    MARKER = "|"

    def split(self, content: str) -> list[str]:
        text = content.strip()
        if not text:
            return []
        return [part for part in (p.strip() for p in text.split(self.MARKER)) if part]


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def store():
    return InMemoryVectorStore()


@pytest.fixture
def service(store, embedder):
    return SemanticSearchService(store, embedder=embedder, chunker=FixedChunker())
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/vector/test_service.py`:

```python
# ABOUTME: Unit tests for SemanticSearchService against the in-memory store and fake embedder.
# ABOUTME: The two-phase hash-skip, both prunes, and the dimension guard are the load-bearing cases.

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    CollectionNotFoundError,
    EmbeddingMismatchError,
    IndexDoc,
    SemanticSearchService,
)

COLLECTION = "kg-nodes"


def test_index_creates_the_collection_registry_row(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit account")])

    info = store.describe(COLLECTION)

    assert info is not None
    assert (info.model, info.dim, info.document_count) == ("fake-embedding", 8, 1)


def test_index_reports_what_it_wrote(service):
    result = service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit account"),
            IndexDoc(parent_id="b", content="invoice payment"),
        ],
    )

    assert result.chunks_written == 2
    assert result.chunks_skipped == 0
    assert result.chunks_pruned == 0
    assert result.documents_pruned == 0


def test_index_splits_documents_into_chunks(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|account|closure")])

    hits = store.search(COLLECTION, [1.0] * 8, top_k=10)

    assert sorted(h.doc_id for h in hits) == ["a#0", "a#1", "a#2"]
    assert sorted(h.content for h in hits) == ["account", "closure", "deposit"]


def test_index_embeds_each_chunk_once_in_a_single_batch(service, embedder):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|account")])

    assert embedder.embed_calls == 1
    assert embedder.embedded_texts == ["deposit", "account"]


def test_reindexing_unchanged_content_costs_zero_embedding_calls(service, embedder):
    docs = [IndexDoc(parent_id="a", content="deposit account")]
    service.index(COLLECTION, docs)
    embedder.document_batches.clear()

    result = service.index(COLLECTION, docs)

    assert embedder.embed_calls == 0
    assert result.chunks_written == 0
    assert result.chunks_skipped == 1


def test_reindexing_embeds_only_the_changed_document(service, embedder):
    service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit account"),
            IndexDoc(parent_id="b", content="invoice payment"),
        ],
    )
    embedder.document_batches.clear()

    result = service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit account"),
            IndexDoc(parent_id="b", content="invoice payment audit"),
        ],
    )

    assert embedder.embedded_texts == ["invoice payment audit"]
    assert (result.chunks_written, result.chunks_skipped) == (1, 1)


def test_index_with_no_documents_does_nothing(service, embedder):
    result = service.index(COLLECTION, [])

    assert embedder.embed_calls == 0
    assert result.chunks_written == 0


def test_index_copies_document_metadata_onto_every_chunk(service, store):
    service.index(
        COLLECTION,
        [IndexDoc(parent_id="a", content="deposit|account", metadata={"path": "a.json"})],
    )

    hits = store.search(COLLECTION, [1.0] * 8, top_k=10)

    assert all(hit.metadata == {"path": "a.json"} for hit in hits)


def test_index_carries_the_family_axes_onto_every_chunk(service, store):
    service.index(
        COLLECTION,
        [
            IndexDoc(
                parent_id="a",
                content="deposit|account",
                scope="fbp-product-deposit-app",
                version="develop",
                kind="Model--DTO",
            )
        ],
    )

    hits = store.search(COLLECTION, [1.0] * 8, top_k=10)

    assert all(
        (h.scope, h.version, h.kind) == ("fbp-product-deposit-app", "develop", "Model--DTO")
        for h in hits
    )


def test_shrinking_a_document_prunes_its_trailing_chunks(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|account|closure")])

    result = service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|account")])

    assert result.chunks_pruned == 1
    assert sorted(h.doc_id for h in store.search(COLLECTION, [1.0] * 8, top_k=10)) == [
        "a#0",
        "a#1",
    ]


def test_chunk_tail_prune_never_touches_a_document_that_grew(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])

    result = service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|account")])

    assert result.chunks_pruned == 0
    assert store.describe(COLLECTION).document_count == 2


def test_indexing_empty_content_prunes_every_chunk_of_that_document(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|account")])

    result = service.index(COLLECTION, [IndexDoc(parent_id="a", content="   ")])

    assert result.chunks_pruned == 2
    assert store.describe(COLLECTION).document_count == 0


def test_family_prune_is_off_by_default(service, store):
    service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit", scope="app", version="v1", kind="LPU"),
            IndexDoc(parent_id="b", content="account", scope="app", version="v1", kind="LPU"),
        ],
    )

    result = service.index(
        COLLECTION,
        [IndexDoc(parent_id="a", content="deposit", scope="app", version="v1", kind="LPU")],
    )

    assert result.documents_pruned == 0
    assert store.describe(COLLECTION).document_count == 2


def test_family_prune_removes_documents_that_left_the_snapshot(service, store):
    service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit", scope="app", version="v1", kind="LPU"),
            IndexDoc(parent_id="b", content="account", scope="app", version="v1", kind="LPU"),
        ],
    )

    result = service.index(
        COLLECTION,
        [IndexDoc(parent_id="a", content="deposit", scope="app", version="v1", kind="LPU")],
        prune=True,
    )

    assert result.documents_pruned == 1
    assert [h.parent_id for h in store.search(COLLECTION, [1.0] * 8, top_k=10)] == ["a"]


def test_family_prune_leaves_other_families_alone(service, store):
    service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit", scope="app", version="v1", kind="LPU"),
            IndexDoc(parent_id="z", content="account", scope="app", version="v1", kind="DTO"),
        ],
    )

    service.index(
        COLLECTION,
        [IndexDoc(parent_id="new", content="closure", scope="app", version="v1", kind="LPU")],
        prune=True,
    )

    remaining = sorted(h.parent_id for h in store.search(COLLECTION, [1.0] * 8, top_k=10))
    assert remaining == ["new", "z"]


def test_family_prune_keeps_hash_skip_working(service, embedder):
    docs = [IndexDoc(parent_id="a", content="deposit", scope="app", version="v1", kind="LPU")]
    service.index(COLLECTION, docs, prune=True)
    embedder.document_batches.clear()

    result = service.index(COLLECTION, docs, prune=True)

    assert embedder.embed_calls == 0
    assert result.chunks_skipped == 1
    assert result.documents_pruned == 0


def test_search_embeds_the_query_and_orders_by_similarity(service, embedder):
    service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="rules", content="deposit account closure rules"),
            IndexDoc(parent_id="invoice", content="invoice payment terms"),
        ],
    )

    hits = service.search(COLLECTION, "deposit account closure", top_k=2)

    assert embedder.queries == ["deposit account closure"]
    assert [h.parent_id for h in hits] == ["rules", "invoice"]
    assert hits[0].score > hits[1].score


def test_search_passes_every_filter_through(service):
    service.index(
        COLLECTION,
        [
            IndexDoc(
                parent_id="a",
                content="deposit account",
                scope="app",
                version="develop",
                kind="LPU",
                metadata={"tier": 1},
            ),
            IndexDoc(
                parent_id="b",
                content="deposit account",
                scope="app",
                version="develop",
                kind="Model--DTO",
                metadata={"tier": 2},
            ),
        ],
    )

    hits = service.search(
        COLLECTION,
        "deposit",
        scope="app",
        version="develop",
        kind="LPU",
        metadata_filter={"tier": 1},
    )

    assert [h.parent_id for h in hits] == ["a"]


def test_search_on_an_unknown_collection_raises_and_does_not_create_it(service, store):
    with pytest.raises(CollectionNotFoundError):
        service.search("never-indexed", "deposit")

    assert store.describe("never-indexed") is None


def test_search_results_carry_parent_id_and_chunk_index_for_regrouping(service):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit|deposit account")])

    hits = service.search(COLLECTION, "deposit account", top_k=5)

    assert {(h.parent_id, h.chunk_index) for h in hits} == {("a", 0), ("a", 1)}


def test_delete_passes_through_and_returns_the_row_count(service, store):
    service.index(
        COLLECTION,
        [
            IndexDoc(parent_id="a", content="deposit", scope="app"),
            IndexDoc(parent_id="b", content="account", scope="app"),
        ],
    )

    assert service.delete(COLLECTION, parent_ids=["a"]) == 1
    assert store.describe(COLLECTION).document_count == 1


def test_delete_on_an_unknown_collection_raises(service):
    with pytest.raises(CollectionNotFoundError):
        service.delete("never-indexed", ids=["a#0"])


def test_describe_passes_through(service):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])

    info = service.describe(COLLECTION)

    assert info is not None
    assert info.name == COLLECTION
    assert service.describe("never-indexed") is None


def test_drop_collection_removes_everything_and_allows_a_fresh_index(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])

    service.drop_collection(COLLECTION)

    assert store.describe(COLLECTION) is None
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])
    assert store.describe(COLLECTION).document_count == 1


def test_dimension_guard_rejects_a_model_change_on_index(store, embedder):
    store.ensure_collection(COLLECTION, model="text-embedding-3-small", dim=8)
    from tests.unit.vector.conftest import FixedChunker

    service = SemanticSearchService(store, embedder=embedder, chunker=FixedChunker())

    with pytest.raises(EmbeddingMismatchError, match="fake-embedding"):
        service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])


def test_dimension_guard_rejects_a_dimension_change_on_search(store, embedder):
    store.ensure_collection(COLLECTION, model="fake-embedding", dim=1536)
    from tests.unit.vector.conftest import FixedChunker

    service = SemanticSearchService(store, embedder=embedder, chunker=FixedChunker())

    with pytest.raises(EmbeddingMismatchError, match="1536"):
        service.search(COLLECTION, "deposit")


def test_dimension_guard_is_checked_once_then_cached(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])
    calls: list[str] = []
    original = store.describe

    def counting_describe(collection):
        calls.append(collection)
        return original(collection)

    store.describe = counting_describe
    service.search(COLLECTION, "deposit")
    service.search(COLLECTION, "account")

    assert calls == []


def test_drop_collection_clears_the_guard_cache(service, store):
    service.index(COLLECTION, [IndexDoc(parent_id="a", content="deposit")])
    service.drop_collection(COLLECTION)
    store.ensure_collection(COLLECTION, model="other-model", dim=8)

    with pytest.raises(EmbeddingMismatchError):
        service.search(COLLECTION, "deposit")
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_service.py -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'SemanticSearchService'`.

- [ ] **Step 4: Write `service.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/service.py`:

```python
# ABOUTME: The surface domains call — wires Chunker + Embedder + VectorStore.
# ABOUTME: Owns two-phase indexing, both prunes, and the embedding-dimension guard.

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.services.vector.chunker import TokenChunker
from autobots_devtools_shared_lib.common.services.vector.embedder import get_embedder
from autobots_devtools_shared_lib.common.services.vector.errors import (
    CollectionNotFoundError,
    EmbeddingMismatchError,
)
from autobots_devtools_shared_lib.common.services.vector.models import (
    IndexResult,
    VectorDoc,
    compute_content_hash,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from autobots_devtools_shared_lib.common.services.vector.chunker import Chunker
    from autobots_devtools_shared_lib.common.services.vector.embedder import Embedder
    from autobots_devtools_shared_lib.common.services.vector.models import (
        CollectionInfo,
        Family,
        IndexDoc,
        ScoredDoc,
    )
    from autobots_devtools_shared_lib.common.services.vector.store import VectorStore

logger = get_logger(__name__)


class SemanticSearchService:
    """Index whole documents and search them semantically.

    Callers hand over documents, never chunks and never vectors: the service
    owns splitting (so nothing can exceed the model's input cap) and embedding
    (so one collection is never mixed across models).
    """

    def __init__(
        self,
        store: VectorStore,
        *,
        embedder: Embedder | None = None,
        chunker: Chunker | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder if embedder is not None else get_embedder()
        self._chunker = chunker if chunker is not None else TokenChunker()
        # Collections already checked against the configured model+dim. The
        # registry row is immutable, so one check per process is enough.
        self._verified: set[str] = set()

    # --- dimension guard ---

    def _check(self, collection: str, info: CollectionInfo) -> None:
        if info.model != self._embedder.model or info.dim != self._embedder.dim:
            msg = (
                f"Collection {collection!r} was indexed with model {info.model!r} "
                f"(dim {info.dim}) but this process is configured for "
                f"{self._embedder.model!r} (dim {self._embedder.dim}). "
                f"Vectors from different models are not comparable — "
                f"drop_collection({collection!r}) and re-index to switch."
            )
            raise EmbeddingMismatchError(msg)
        self._verified.add(collection)

    def _verify_for_index(self, collection: str) -> None:
        """Verify the collection, creating its registry row when absent."""
        if collection in self._verified:
            return
        info = self._store.describe(collection)
        if info is None:
            info = self._store.ensure_collection(
                collection, model=self._embedder.model, dim=self._embedder.dim
            )
        self._check(collection, info)

    def _verify_for_search(self, collection: str) -> None:
        """Verify the collection, refusing to create it — reads never register."""
        if collection in self._verified:
            return
        info = self._store.describe(collection)
        if info is None:
            raise CollectionNotFoundError(collection)
        self._check(collection, info)

    # --- write path ---

    def index(
        self, collection: str, docs: Sequence[IndexDoc], *, prune: bool = False
    ) -> IndexResult:
        """Chunk, embed, and upsert `docs`; return what changed.

        Idempotent: re-indexing identical content performs no embedding call and
        no write. `prune=True` additionally removes documents that have left the
        batch's families, making "re-index this snapshot" a single call.
        """
        self._verify_for_index(collection)

        vector_docs: list[VectorDoc] = []
        chunk_counts: dict[str, int] = {}
        parents_by_family: defaultdict[Family, set[str]] = defaultdict(set)

        for doc in docs:
            chunks = self._chunker.split(doc.content)
            chunk_counts[doc.parent_id] = len(chunks)
            parents_by_family[doc.family].add(doc.parent_id)
            metadata = dict(doc.metadata)
            vector_docs.extend(
                VectorDoc(
                    parent_id=doc.parent_id,
                    chunk_index=index,
                    content=chunk,
                    content_hash=compute_content_hash(chunk),
                    scope=doc.scope,
                    version=doc.version,
                    kind=doc.kind,
                    metadata=metadata,
                )
                for index, chunk in enumerate(chunks)
            )

        phase_one = self._store.upsert(collection, vector_docs)
        written = 0
        if phase_one.needs_embedding:
            pending_ids = set(phase_one.needs_embedding)
            pending = [doc for doc in vector_docs if doc.doc_id in pending_ids]
            vectors = self._embedder.embed_documents([doc.content for doc in pending])
            embedded = [
                replace(doc, embedding=vector)
                for doc, vector in zip(pending, vectors, strict=True)
            ]
            written = len(self._store.upsert(collection, embedded).written)

        pruned_chunks = self._prune_chunk_tails(collection, chunk_counts)
        pruned_documents = (
            self._prune_families(collection, parents_by_family) if prune else 0
        )

        return IndexResult(
            chunks_written=written,
            chunks_skipped=len(phase_one.skipped),
            chunks_pruned=pruned_chunks,
            documents_pruned=pruned_documents,
        )

    def _prune_chunk_tails(self, collection: str, chunk_counts: Mapping[str, int]) -> int:
        """Drop chunks past the new end of each document.

        Parents are grouped by chunk count so a snapshot of thousands of
        single-chunk documents costs one DELETE, not thousands.
        """
        if not chunk_counts:
            return 0
        by_count: defaultdict[int, list[str]] = defaultdict(list)
        for parent_id, count in chunk_counts.items():
            by_count[count].append(parent_id)
        return sum(
            self._store.delete(collection, parent_ids=parents, min_chunk_index=count)
            for count, parents in by_count.items()
        )

    def _prune_families(
        self, collection: str, parents_by_family: Mapping[Family, set[str]]
    ) -> int:
        """Drop documents in the batch's families that were absent from the batch."""
        return sum(
            self._store.prune_missing(collection, family, sorted(parent_ids))
            for family, parent_ids in parents_by_family.items()
        )

    # --- read path ---

    def search(
        self,
        collection: str,
        query: str,
        *,
        top_k: int = 5,
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[ScoredDoc]:
        """Embed `query` and return the closest chunks, highest cosine similarity first.

        Hits are chunks; regrouping them by `parent_id` is the caller's concern.
        """
        self._verify_for_search(collection)
        query_embedding = self._embedder.embed_query(query)
        return self._store.search(
            collection,
            query_embedding,
            top_k=top_k,
            scope=scope,
            version=version,
            kind=kind,
            metadata_filter=metadata_filter,
        )

    def describe(self, collection: str) -> CollectionInfo | None:
        return self._store.describe(collection)

    # --- delete path ---

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        *,
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        parent_ids: Sequence[str] | None = None,
    ) -> int:
        """Delete rows matching every supplied criterion; return the row count."""
        return self._store.delete(
            collection,
            ids,
            scope=scope,
            version=version,
            kind=kind,
            parent_ids=parent_ids,
        )

    def drop_collection(self, collection: str) -> None:
        """Remove the collection entirely. The recovery path for a model switch."""
        self._store.drop_collection(collection)
        self._verified.discard(collection)
        logger.info("Dropped vector collection %s", collection)
```

- [ ] **Step 5: Export the new name**

In `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`, add:

```python
from autobots_devtools_shared_lib.common.services.vector.service import SemanticSearchService
```

and add `"SemanticSearchService"` to `__all__` in sorted position.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector -v --no-cov
```

Expected: PASS — the whole vector suite, 90+ tests.

- [ ] **Step 7: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): SemanticSearchService with two-phase indexing and prunes"
```

---

### Task 6: Service singleton wiring

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/factory.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/unit/vector/test_factory.py`

**Interfaces:**
- Consumes: `SemanticSearchService` (Task 5).
- Produces: `set_semantic_search_service(service: SemanticSearchService) -> None`,
  `get_semantic_search_service() -> SemanticSearchService` (raises `VectorConfigError`
  when unset), `reset_semantic_search_service() -> None` (test hook), and the module
  global `_SEMANTIC_SEARCH_SINGLETON`. Tasks 9 and 10 resolve the service through
  `get_semantic_search_service`.

Mirrors `set_context_store()` in `common/services/context/factory.py`, with one
deliberate difference: there is **no** YAML/env fallback. A vector service needs a
domain-supplied sessionmaker, which shared-lib cannot invent, so an unset singleton
is a startup bug and fails loudly rather than silently falling back to an in-memory
store that would look like it worked.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/test_factory.py`:

```python
# ABOUTME: Unit tests for the semantic-search service singleton.
# ABOUTME: Domains inject at startup; the tool and router resolve through get_*.

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    InMemoryVectorStore,
    SemanticSearchService,
    VectorConfigError,
    get_semantic_search_service,
    reset_semantic_search_service,
    set_semantic_search_service,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_semantic_search_service()
    yield
    reset_semantic_search_service()


def test_get_before_set_raises_with_actionable_guidance():
    with pytest.raises(VectorConfigError, match="set_semantic_search_service"):
        get_semantic_search_service()


def test_set_then_get_returns_the_same_instance(embedder):
    service = SemanticSearchService(InMemoryVectorStore(), embedder=embedder)

    set_semantic_search_service(service)

    assert get_semantic_search_service() is service


def test_set_replaces_a_previous_instance(embedder):
    first = SemanticSearchService(InMemoryVectorStore(), embedder=embedder)
    second = SemanticSearchService(InMemoryVectorStore(), embedder=embedder)
    set_semantic_search_service(first)

    set_semantic_search_service(second)

    assert get_semantic_search_service() is second


def test_reset_clears_the_singleton(embedder):
    set_semantic_search_service(
        SemanticSearchService(InMemoryVectorStore(), embedder=embedder)
    )

    reset_semantic_search_service()

    with pytest.raises(VectorConfigError):
        get_semantic_search_service()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_factory.py -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'VectorConfigError'`.

- [ ] **Step 3: Add `VectorConfigError` to `errors.py`**

Append to `src/autobots_devtools_shared_lib/common/services/vector/errors.py`:

```python
class VectorConfigError(VectorStoreError):
    """Raised when the semantic search service was never wired up at startup."""
```

- [ ] **Step 4: Write `factory.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/factory.py`:

```python
# ABOUTME: Module-level singleton for the semantic search service.
# ABOUTME: Domains inject at startup; the agent tool and router resolve through it.

from __future__ import annotations

from typing import TYPE_CHECKING

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.services.vector.errors import VectorConfigError

if TYPE_CHECKING:
    from autobots_devtools_shared_lib.common.services.vector.service import (
        SemanticSearchService,
    )

logger = get_logger(__name__)

_SEMANTIC_SEARCH_SINGLETON: SemanticSearchService | None = None


def set_semantic_search_service(service: SemanticSearchService) -> None:
    """Register the process-wide semantic search service.

    Call once at server startup, after the domain has built its store with its
    own sessionmaker.
    """
    global _SEMANTIC_SEARCH_SINGLETON
    _SEMANTIC_SEARCH_SINGLETON = service
    logger.info("Semantic search service registered")


def get_semantic_search_service() -> SemanticSearchService:
    """Return the registered service.

    Unlike get_context_store() there is no fallback: the service needs a
    domain-supplied sessionmaker, so an unset singleton is a startup bug and
    must not be papered over with an in-memory store that silently loses data.
    """
    if _SEMANTIC_SEARCH_SINGLETON is None:
        msg = (
            "No semantic search service registered. Construct a "
            "SemanticSearchService with your PgVectorStore at startup and call "
            "set_semantic_search_service(service)."
        )
        raise VectorConfigError(msg)
    return _SEMANTIC_SEARCH_SINGLETON


def reset_semantic_search_service() -> None:
    """Clear the singleton. Test hook; not for production code paths."""
    global _SEMANTIC_SEARCH_SINGLETON
    _SEMANTIC_SEARCH_SINGLETON = None
```

- [ ] **Step 5: Export the new names**

In `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`, add:

```python
from autobots_devtools_shared_lib.common.services.vector.factory import (
    get_semantic_search_service,
    reset_semantic_search_service,
    set_semantic_search_service,
)
```

Add `VectorConfigError` to the existing `errors` import block, and add
`"VectorConfigError"`, `"get_semantic_search_service"`,
`"reset_semantic_search_service"`, `"set_semantic_search_service"` to `__all__`
in sorted position.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector -v --no-cov
```

Expected: PASS.

- [ ] **Step 7: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): semantic search service singleton"
```

---

### Task 7: SQL schema and loader

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/schema.sql`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/factory.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/unit/vector/test_factory.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `vector_schema_sql() -> str`, returning the shipped DDL. Task 8's
  integration fixture applies it; domains apply it through their own migration
  pipeline.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/vector/test_factory.py`:

```python
def test_vector_schema_sql_ships_the_full_ddl():
    from autobots_devtools_shared_lib.common.services.vector import vector_schema_sql

    sql = vector_schema_sql()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    for table in ("vector_collections", "vector_document_family", "vector_documents"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "UNIQUE NULLS NOT DISTINCT" in sql
    assert "USING hnsw (embedding vector_cosine_ops)" in sql
    assert "jsonb_path_ops" in sql
    assert "vector(1536)" in sql
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
../.venv/bin/pytest tests/unit/vector/test_factory.py -k schema -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'vector_schema_sql'`.

- [ ] **Step 3: Write `schema.sql`**

Create `src/autobots_devtools_shared_lib/common/services/vector/schema.sql`:

```sql
-- Semantic search schema for autobots-devtools-shared-lib.
-- Requires PostgreSQL >= 15 (UNIQUE NULLS NOT DISTINCT) and pgvector >= 0.8
-- (iterative index scans, which keep filtered HNSW searches from under-returning).
-- Idempotent: safe to apply repeatedly from a domain's migration pipeline.
--
-- The vector(1536) column is pinned to text-embedding-3-small's native size.
-- Changing the embedding_dim setting requires a migration here, not just a
-- settings change.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vector_collections (
    name        text PRIMARY KEY,          -- "kg-nodes", "kbe-articles"
    model       text NOT NULL,             -- "text-embedding-3-small"
    dim         smallint NOT NULL,         -- 1536
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vector_document_family (
    id          int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collection  text NOT NULL REFERENCES vector_collections(name)
                    ON DELETE CASCADE,
    scope       text,                      -- component/repo, e.g. "fbp-product-deposit-app"
    version     text,                      -- "develop", "v1", "v1.1"
    kind        text,                      -- node/doc type, e.g. "Model--DTO", "LPU"
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (collection, scope, version, kind)
);

CREATE TABLE IF NOT EXISTS vector_documents (
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

CREATE INDEX IF NOT EXISTS idx_vd_embedding ON vector_documents
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_vd_family    ON vector_documents (collection, family_id);
CREATE INDEX IF NOT EXISTS idx_vd_parent    ON vector_documents (collection, family_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_vd_metadata  ON vector_documents
    USING gin (metadata jsonb_path_ops);
```

- [ ] **Step 4: Add the loader to `factory.py`**

Append to `src/autobots_devtools_shared_lib/common/services/vector/factory.py`:

```python
def vector_schema_sql() -> str:
    """Return the shipped DDL for the vector tables.

    shared-lib ships the SQL but never runs it: each domain applies it through
    its own migration pipeline, so nothing here assumes migration tooling.
    """
    return (
        resources.files("autobots_devtools_shared_lib.common.services.vector")
        .joinpath("schema.sql")
        .read_text(encoding="utf-8")
    )
```

and add `from importlib import resources` to the imports at the top of the file.

- [ ] **Step 5: Confirm the SQL ships in the built package**

```bash
../.venv/bin/python -c "
from autobots_devtools_shared_lib.common.services.vector import vector_schema_sql
print(len(vector_schema_sql()), 'chars')
"
```

Expected: a character count around 2500, no exception. Poetry includes non-Python
files inside the package directory, so no `include` entry in `pyproject.toml` is
needed — but if the count fails after a `poetry build`, add
`include = [{ path = "src/autobots_devtools_shared_lib/**/*.sql", format = ["sdist", "wheel"] }]`
under `[tool.poetry]`.

- [ ] **Step 6: Export and run the tests**

In `__init__.py` add `vector_schema_sql` to the existing `factory` import block and
to `__all__`, then:

```bash
../.venv/bin/pytest tests/unit/vector -v --no-cov
```

Expected: PASS.

- [ ] **Step 7: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/unit/vector
git commit -m "feat(vector): ship idempotent pgvector schema and loader"
```

---

### Task 8: PgVectorStore and its integration tests

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/services/vector/pg_store.py`
- Modify: `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`
- Test: `tests/integration/test_pgvector_store.py`

**Interfaces:**
- Consumes: the `VectorStore` Protocol and every model type (Tasks 1, 4);
  `vector_schema_sql()` (Task 7).
- Produces: `PgVectorStore(session_factory: sessionmaker[Session])` — the same
  seven methods as `InMemoryVectorStore`, with identical semantics. Task 11's
  README documents the constructor; nothing else imports it.

**SQL notes the implementer must not improvise around:**

- **Null-safe binds.** `IS NOT DISTINCT FROM :scope` fails to infer a type when
  the value is `NULL`. Every null-comparable bind is wrapped:
  `IS NOT DISTINCT FROM CAST(:scope AS text)`.
- **Wildcard filters** use `(CAST(:scope AS text) IS NULL OR f.scope = :scope)`,
  matching the in-memory `_axes_match` rule exactly.
- **Vector binds** use `bindparam("q", type_=Vector())` from
  `pgvector.sqlalchemy` — its bind processor turns a Python list into pgvector's
  `'[1,2,3]'` literal, so no per-connection `register_vector` call is needed.
- **Score** is `1 - (embedding <=> :q)`: `<=>` is cosine *distance*, and the
  Protocol promises *similarity*.
- **`ORDER BY embedding <=> :q`** must use the raw distance operator, not the
  computed `score` alias — only the operator form uses the HNSW index.
- **Array binds** use `bindparam("ids", type_=ARRAY(String))` with
  `= ANY(:ids)`, which has no parameter-count ceiling (unlike `IN` expansion).
- **`metadata @> CAST(:filter AS jsonb)`** with `json.dumps(...)`, and
  `matches_metadata({}, metadata_filter)` is called first purely to raise the
  same `ValueError` on non-scalar values that the fake raises.

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/test_pgvector_store.py`:

```python
# ABOUTME: PgVectorStore against a real Postgres with pgvector.
# ABOUTME: Mirrors tests/unit/vector/test_in_memory_store.py — same asserts, real SQL.

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from autobots_devtools_shared_lib.common.services.vector import (
    CollectionNotFoundError,
    Family,
    PgVectorStore,
    VectorDoc,
    VectorStore,
    compute_content_hash,
    vector_schema_sql,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("VECTOR_TEST_DATABASE_URL", "")
COLLECTION = "test-kg-nodes"
DIM = 1536


def _vec(*leading: float) -> list[float]:
    """A DIM-length vector whose first entries are `leading` and the rest zeros."""
    return [*leading, *([0.0] * (DIM - len(leading)))]


@pytest.fixture(scope="module")
def session_factory():
    if not DATABASE_URL:
        pytest.skip("VECTOR_TEST_DATABASE_URL not set")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as connection:
        for statement in vector_schema_sql().split(";"):
            if statement.strip():
                connection.execute(text(statement))
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def store(session_factory):
    store = PgVectorStore(session_factory)
    store.drop_collection(COLLECTION)
    store.ensure_collection(COLLECTION, model="text-embedding-3-small", dim=DIM)
    yield store
    store.drop_collection(COLLECTION)


def make_doc(parent_id, chunk_index=0, content="body", embedding=None, **axes):
    return VectorDoc(
        parent_id=parent_id,
        chunk_index=chunk_index,
        content=content,
        content_hash=compute_content_hash(content),
        embedding=embedding,
        **axes,
    )


def test_satisfies_the_protocol(store):
    assert isinstance(store, VectorStore)


def test_ensure_collection_is_idempotent_under_a_second_registration(store):
    again = store.ensure_collection(COLLECTION, model="other-model", dim=999)

    assert (again.model, again.dim) == ("text-embedding-3-small", DIM)


def test_upsert_round_trip(store):
    store.upsert(COLLECTION, [make_doc("a", content="deposit", embedding=_vec(1.0))])

    hits = store.search(COLLECTION, _vec(1.0), top_k=5)

    assert [(h.doc_id, h.content) for h in hits] == [("a#0", "deposit")]
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)


def test_upsert_skips_unchanged_hashes_and_flags_changed_ones(store):
    store.upsert(COLLECTION, [make_doc("a", content="same", embedding=_vec(1.0))])

    unchanged = store.upsert(COLLECTION, [make_doc("a", content="same")])
    changed = store.upsert(COLLECTION, [make_doc("a", content="different")])

    assert unchanged.skipped == ("a#0",)
    assert unchanged.needs_embedding == ()
    assert changed.needs_embedding == ("a#0",)


def test_upsert_conflict_updates_the_row_in_place(store):
    store.upsert(COLLECTION, [make_doc("a", content="old", embedding=_vec(1.0))])
    store.upsert(COLLECTION, [make_doc("a", content="new", embedding=_vec(0.0, 1.0))])

    hits = store.search(COLLECTION, _vec(0.0, 1.0), top_k=5)

    assert [(h.doc_id, h.content) for h in hits] == [("a#0", "new")]
    assert store.describe(COLLECTION).document_count == 1


def test_upsert_refreshes_updated_at_on_change(store, session_factory):
    store.upsert(COLLECTION, [make_doc("a", content="old", embedding=_vec(1.0))])
    with session_factory() as session:
        before = session.execute(
            text("SELECT updated_at FROM vector_documents WHERE doc_id = 'a#0'")
        ).scalar_one()

    store.upsert(COLLECTION, [make_doc("a", content="new", embedding=_vec(1.0))])
    with session_factory() as session:
        after = session.execute(
            text("SELECT updated_at FROM vector_documents WHERE doc_id = 'a#0'")
        ).scalar_one()

    assert after > before


def test_search_orders_by_cosine_similarity_descending(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("near", content="n", embedding=_vec(1.0)),
            make_doc("mid", content="m", embedding=_vec(1.0, 1.0)),
            make_doc("far", content="f", embedding=_vec(0.0, 1.0)),
        ],
    )

    hits = store.search(COLLECTION, _vec(1.0), top_k=3)

    assert [h.parent_id for h in hits] == ["near", "mid", "far"]
    assert hits[0].score > hits[1].score > hits[2].score


def test_family_rows_are_created_once_and_reused(store, session_factory):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", content="x", embedding=_vec(1.0), scope="app", kind="LPU"),
            make_doc("b", content="y", embedding=_vec(1.0), scope="app", kind="LPU"),
        ],
    )

    with session_factory() as session:
        count = session.execute(
            text("SELECT count(*) FROM vector_document_family WHERE collection = :c"),
            {"c": COLLECTION},
        ).scalar_one()

    assert count == 1


def test_search_filters_resolve_through_the_family_table(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", content="x", embedding=_vec(1.0), scope="app", version="develop", kind="LPU"),
            make_doc("b", content="y", embedding=_vec(1.0), scope="app", version="develop", kind="DTO"),
            make_doc("c", content="z", embedding=_vec(1.0), scope="other", version="develop", kind="LPU"),
        ],
    )

    assert sorted(h.parent_id for h in store.search(COLLECTION, _vec(1.0), kind="LPU")) == [
        "a",
        "c",
    ]
    assert [
        h.parent_id
        for h in store.search(COLLECTION, _vec(1.0), scope="app", version="develop", kind="LPU")
    ] == ["a"]


def test_search_returns_family_axes_and_metadata(store):
    store.upsert(
        COLLECTION,
        [
            VectorDoc(
                parent_id="a",
                chunk_index=0,
                content="x",
                content_hash="h",
                scope="app",
                version="develop",
                kind="LPU",
                metadata={"path": "a.json", "tier": 1},
                embedding=_vec(1.0),
            )
        ],
    )

    hit = store.search(COLLECTION, _vec(1.0))[0]

    assert (hit.scope, hit.version, hit.kind) == ("app", "develop", "LPU")
    assert hit.metadata == {"path": "a.json", "tier": 1}


def test_metadata_containment_filter(store):
    store.upsert(
        COLLECTION,
        [
            VectorDoc(
                parent_id=pid,
                chunk_index=0,
                content=pid,
                content_hash=compute_content_hash(pid),
                metadata={"tier": tier},
                embedding=_vec(1.0),
            )
            for pid, tier in (("a", 1), ("b", 2))
        ],
    )

    hits = store.search(COLLECTION, _vec(1.0), metadata_filter={"tier": 1})

    assert [h.parent_id for h in hits] == ["a"]


def test_metadata_filter_rejects_non_scalar_values(store):
    with pytest.raises(ValueError, match="scalar"):
        store.search(COLLECTION, _vec(1.0), metadata_filter={"terms": ["x"]})


def test_delete_by_ids_parents_and_chunk_tail(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", chunk_index=i, content=f"c{i}", embedding=_vec(1.0))
            for i in range(4)
        ]
        + [make_doc("b", content="b0", embedding=_vec(1.0))],
    )

    assert store.delete(COLLECTION, parent_ids=["a"], min_chunk_index=2) == 2
    assert store.delete(COLLECTION, ids=["a#0"]) == 1
    assert store.delete(COLLECTION, parent_ids=["b"]) == 1
    assert store.describe(COLLECTION).document_count == 1


def test_delete_by_scope_and_version(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("a", content="x", embedding=_vec(1.0), scope="app", version="v1"),
            make_doc("b", content="y", embedding=_vec(1.0), scope="app", version="v2"),
        ],
    )

    assert store.delete(COLLECTION, scope="app", version="v1") == 1
    assert [h.parent_id for h in store.search(COLLECTION, _vec(1.0))] == ["b"]


def test_delete_without_criteria_raises(store):
    with pytest.raises(ValueError, match="at least one"):
        store.delete(COLLECTION)


def test_delete_with_an_unmatched_family_deletes_nothing(store):
    store.upsert(COLLECTION, [make_doc("a", content="x", embedding=_vec(1.0), scope="app")])

    assert store.delete(COLLECTION, scope="absent") == 0
    assert store.describe(COLLECTION).document_count == 1


def test_prune_missing_matches_the_family_exactly_including_nulls(store):
    store.upsert(
        COLLECTION,
        [
            make_doc("keep", content="k", embedding=_vec(1.0), scope="app", version="develop", kind="LPU"),
            make_doc("gone", content="g", embedding=_vec(1.0), scope="app", version="develop", kind="LPU"),
            make_doc("other", content="o", embedding=_vec(1.0), scope="app", version="develop", kind="DTO"),
            make_doc("nulls", content="n", embedding=_vec(1.0)),
        ],
    )

    assert store.prune_missing(COLLECTION, Family("app", "develop", "LPU"), ["keep"]) == 1
    assert store.prune_missing(COLLECTION, Family(None, None, None), []) == 1
    assert sorted(h.parent_id for h in store.search(COLLECTION, _vec(1.0), top_k=10)) == [
        "keep",
        "other",
    ]


def test_prune_missing_with_an_empty_keep_list_clears_the_family(store):
    store.upsert(COLLECTION, [make_doc("a", content="x", embedding=_vec(1.0), scope="app")])

    assert store.prune_missing(COLLECTION, Family("app", None, None), []) == 1


def test_unknown_collection_raises_on_every_read_and_write(store):
    for call in (
        lambda: store.upsert("absent", [make_doc("a", embedding=_vec(1.0))]),
        lambda: store.search("absent", _vec(1.0)),
        lambda: store.delete("absent", ids=["a#0"]),
        lambda: store.prune_missing("absent", Family(), []),
    ):
        with pytest.raises(CollectionNotFoundError):
            call()


def test_drop_collection_cascades_families_and_documents(store, session_factory):
    store.upsert(COLLECTION, [make_doc("a", content="x", embedding=_vec(1.0), scope="app")])

    store.drop_collection(COLLECTION)

    assert store.describe(COLLECTION) is None
    with session_factory() as session:
        families = session.execute(
            text("SELECT count(*) FROM vector_document_family WHERE collection = :c"),
            {"c": COLLECTION},
        ).scalar_one()
        documents = session.execute(
            text("SELECT count(*) FROM vector_documents WHERE collection = :c"),
            {"c": COLLECTION},
        ).scalar_one()

    assert (families, documents) == (0, 0)
    store.drop_collection(COLLECTION)  # idempotent


def test_search_uses_the_hnsw_index(store, session_factory):
    store.upsert(
        COLLECTION,
        [
            make_doc(f"d{i}", content=f"c{i}", embedding=_vec(float(i), 1.0))
            for i in range(50)
        ],
    )
    with session_factory() as session:
        session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            row[0]
            for row in session.execute(
                text(
                    "EXPLAIN SELECT doc_id FROM vector_documents "
                    "WHERE collection = :c ORDER BY embedding <=> "
                    "CAST(:q AS vector) LIMIT 5"
                ),
                {"c": COLLECTION, "q": str(_vec(1.0))},
            )
        )

    assert "idx_vd_embedding" in plan
```

- [ ] **Step 2: Start Postgres with pgvector and run the tests to verify they fail**

```bash
docker run -d --name pgvector-test -e POSTGRES_PASSWORD=postgres -p 5433:5432 pgvector/pgvector:pg16
export VECTOR_TEST_DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5433/postgres"
../.venv/bin/pytest tests/integration/test_pgvector_store.py -v --no-cov
```

Expected: FAIL with `ImportError: cannot import name 'PgVectorStore'`. If Docker
is unavailable, the tests skip instead — that is a blocked task, not a passing
one; say so rather than moving on.

- [ ] **Step 3: Write `pg_store.py`**

Create `src/autobots_devtools_shared_lib/common/services/vector/pg_store.py`:

```python
# ABOUTME: SQLAlchemy + pgvector VectorStore. Sync, matching MER's psycopg2 DB layer.
# ABOUTME: The domain supplies the sessionmaker; shared-lib never owns connection config.

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY

from autobots_devtools_shared_lib.common.services.vector.errors import CollectionNotFoundError
from autobots_devtools_shared_lib.common.services.vector.models import (
    CollectionInfo,
    Family,
    ScoredDoc,
    UpsertResult,
)
from autobots_devtools_shared_lib.common.services.vector.vector_math import matches_metadata

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy.orm import Session, sessionmaker

    from autobots_devtools_shared_lib.common.services.vector.models import VectorDoc

_SELECT_COLLECTION = text(
    """
    SELECT c.name, c.model, c.dim,
           (SELECT count(*) FROM vector_documents d WHERE d.collection = c.name)
               AS document_count
    FROM vector_collections c
    WHERE c.name = :collection
    """
)

_INSERT_COLLECTION = text(
    """
    INSERT INTO vector_collections (name, model, dim)
    VALUES (:collection, :model, :dim)
    ON CONFLICT (name) DO NOTHING
    """
)

_DELETE_COLLECTION = text("DELETE FROM vector_collections WHERE name = :collection")

_INSERT_FAMILY = text(
    """
    INSERT INTO vector_document_family (collection, scope, version, kind)
    VALUES (:collection, CAST(:scope AS text), CAST(:version AS text), CAST(:kind AS text))
    ON CONFLICT (collection, scope, version, kind) DO NOTHING
    """
)

_SELECT_FAMILY_EXACT = text(
    """
    SELECT id FROM vector_document_family
    WHERE collection = :collection
      AND scope   IS NOT DISTINCT FROM CAST(:scope AS text)
      AND version IS NOT DISTINCT FROM CAST(:version AS text)
      AND kind    IS NOT DISTINCT FROM CAST(:kind AS text)
    """
)

# Wildcard resolution: a NULL bind constrains nothing, matching InMemoryVectorStore.
_SELECT_FAMILY_IDS = text(
    """
    SELECT id FROM vector_document_family
    WHERE collection = :collection
      AND (CAST(:scope AS text)   IS NULL OR scope = :scope)
      AND (CAST(:version AS text) IS NULL OR version = :version)
      AND (CAST(:kind AS text)    IS NULL OR kind = :kind)
    """
)

_SELECT_HASHES = text(
    """
    SELECT doc_id, content_hash FROM vector_documents
    WHERE collection = :collection AND doc_id = ANY(:ids)
    """
).bindparams(bindparam("ids", type_=ARRAY(String)))

_UPSERT_DOCUMENT = text(
    """
    INSERT INTO vector_documents (
        collection, family_id, parent_id, chunk_index, doc_id,
        content, content_hash, metadata, embedding
    )
    VALUES (
        :collection, :family_id, :parent_id, :chunk_index, :doc_id,
        :content, :content_hash, CAST(:metadata AS jsonb), :embedding
    )
    ON CONFLICT (collection, doc_id) DO UPDATE SET
        family_id    = EXCLUDED.family_id,
        parent_id    = EXCLUDED.parent_id,
        chunk_index  = EXCLUDED.chunk_index,
        content      = EXCLUDED.content,
        content_hash = EXCLUDED.content_hash,
        metadata     = EXCLUDED.metadata,
        embedding    = EXCLUDED.embedding,
        updated_at   = now()
    """
).bindparams(bindparam("embedding", type_=Vector()))

_PRUNE_MISSING = text(
    """
    DELETE FROM vector_documents d
    USING vector_document_family f
    WHERE d.family_id = f.id
      AND d.collection = :collection
      AND f.scope   IS NOT DISTINCT FROM CAST(:scope AS text)
      AND f.version IS NOT DISTINCT FROM CAST(:version AS text)
      AND f.kind    IS NOT DISTINCT FROM CAST(:kind AS text)
      AND NOT (d.parent_id = ANY(:keep))
    """
).bindparams(bindparam("keep", type_=ARRAY(String)))


class PgVectorStore:
    """VectorStore over Postgres + pgvector.

    Semantics are identical to InMemoryVectorStore by construction, which is what
    lets unit tests against the fake predict production behaviour.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    # --- collections ---

    def ensure_collection(self, collection: str, *, model: str, dim: int) -> CollectionInfo:
        with self._session_factory() as session:
            session.execute(
                _INSERT_COLLECTION, {"collection": collection, "model": model, "dim": dim}
            )
            session.commit()
            info = self._describe(session, collection)
        if info is None:  # pragma: no cover - the INSERT above guarantees a row
            raise CollectionNotFoundError(collection)
        return info

    def describe(self, collection: str) -> CollectionInfo | None:
        with self._session_factory() as session:
            return self._describe(session, collection)

    def _describe(self, session: Session, collection: str) -> CollectionInfo | None:
        row = session.execute(_SELECT_COLLECTION, {"collection": collection}).first()
        if row is None:
            return None
        return CollectionInfo(
            name=row.name, model=row.model, dim=row.dim, document_count=row.document_count
        )

    def drop_collection(self, collection: str) -> None:
        with self._session_factory() as session:
            session.execute(_DELETE_COLLECTION, {"collection": collection})
            session.commit()

    def _require(self, session: Session, collection: str) -> None:
        if self._describe(session, collection) is None:
            raise CollectionNotFoundError(collection)

    # --- families ---

    def _family_id(self, session: Session, collection: str, family: Family) -> int:
        """Get-or-create the family row. Concurrent creators converge on one row."""
        params = {
            "collection": collection,
            "scope": family.scope,
            "version": family.version,
            "kind": family.kind,
        }
        session.execute(_INSERT_FAMILY, params)
        return session.execute(_SELECT_FAMILY_EXACT, params).scalar_one()

    def _family_ids(
        self,
        session: Session,
        collection: str,
        *,
        scope: str | None,
        version: str | None,
        kind: str | None,
    ) -> list[int]:
        rows = session.execute(
            _SELECT_FAMILY_IDS,
            {"collection": collection, "scope": scope, "version": version, "kind": kind},
        )
        return [row.id for row in rows]

    # --- write path ---

    def upsert(self, collection: str, docs: Sequence[VectorDoc]) -> UpsertResult:
        if not docs:
            with self._session_factory() as session:
                self._require(session, collection)
            return UpsertResult()

        with self._session_factory() as session:
            self._require(session, collection)

            existing = dict(
                session.execute(
                    _SELECT_HASHES,
                    {"collection": collection, "ids": [doc.doc_id for doc in docs]},
                ).all()
            )

            written: list[str] = []
            skipped: list[str] = []
            needs: list[str] = []
            payloads: list[dict[str, Any]] = []

            for doc in docs:
                if existing.get(doc.doc_id) == doc.content_hash:
                    skipped.append(doc.doc_id)
                    continue
                if doc.embedding is None:
                    needs.append(doc.doc_id)
                    continue
                payloads.append(
                    {
                        "collection": collection,
                        "family_id": self._family_id(session, collection, doc.family),
                        "parent_id": doc.parent_id,
                        "chunk_index": doc.chunk_index,
                        "doc_id": doc.doc_id,
                        "content": doc.content,
                        "content_hash": doc.content_hash,
                        "metadata": json.dumps(dict(doc.metadata)),
                        "embedding": list(doc.embedding),
                    }
                )
                written.append(doc.doc_id)

            if payloads:
                session.execute(_UPSERT_DOCUMENT, payloads)
            session.commit()

        return UpsertResult(tuple(written), tuple(skipped), tuple(needs))

    # --- read path ---

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
    ) -> list[ScoredDoc]:
        # Raises the same ValueError the fake raises for non-scalar filter values.
        matches_metadata({}, metadata_filter)

        with self._session_factory() as session:
            self._require(session, collection)

            params: dict[str, Any] = {
                "collection": collection,
                "q": list(query_embedding),
                "top_k": top_k,
            }
            clauses = ["d.collection = :collection"]

            if scope is not None or version is not None or kind is not None:
                family_ids = self._family_ids(
                    session, collection, scope=scope, version=version, kind=kind
                )
                if not family_ids:
                    return []
                clauses.append("d.family_id = ANY(:family_ids)")
                params["family_ids"] = family_ids

            if metadata_filter:
                clauses.append("d.metadata @> CAST(:metadata_filter AS jsonb)")
                params["metadata_filter"] = json.dumps(dict(metadata_filter))

            statement = text(
                f"""
                SELECT d.doc_id, d.parent_id, d.chunk_index, d.content, d.metadata,
                       f.scope, f.version, f.kind,
                       1 - (d.embedding <=> :q) AS score
                FROM vector_documents d
                JOIN vector_document_family f ON f.id = d.family_id
                WHERE {" AND ".join(clauses)}
                ORDER BY d.embedding <=> :q
                LIMIT :top_k
                """  # noqa: S608 - clauses are literals chosen above, never caller text
            ).bindparams(
                bindparam("q", type_=Vector()),
                *(
                    [bindparam("family_ids", type_=ARRAY(String().with_variant(String, "postgresql")))]
                    if "family_ids" in params
                    else []
                ),
            )
            rows = session.execute(statement, params).all()

        return [
            ScoredDoc(
                doc_id=row.doc_id,
                parent_id=row.parent_id,
                chunk_index=row.chunk_index,
                content=row.content,
                score=float(row.score),
                scope=row.scope,
                version=row.version,
                kind=row.kind,
                metadata=dict(row.metadata or {}),
            )
            for row in rows
        ]

    # --- delete path ---

    def delete(
        self,
        collection: str,
        ids: Sequence[str] | None = None,
        *,
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        parent_ids: Sequence[str] | None = None,
        min_chunk_index: int | None = None,
    ) -> int:
        criteria = (ids, scope, version, kind, parent_ids, min_chunk_index)
        if all(criterion is None for criterion in criteria):
            msg = (
                "delete() requires at least one criterion "
                "(ids, parent_ids, scope, version, kind, min_chunk_index); "
                "use drop_collection() to empty a collection."
            )
            raise ValueError(msg)

        with self._session_factory() as session:
            self._require(session, collection)

            params: dict[str, Any] = {"collection": collection}
            clauses = ["collection = :collection"]
            binds = []

            if ids is not None:
                clauses.append("doc_id = ANY(:ids)")
                params["ids"] = list(ids)
                binds.append(bindparam("ids", type_=ARRAY(String)))
            if parent_ids is not None:
                clauses.append("parent_id = ANY(:parent_ids)")
                params["parent_ids"] = list(parent_ids)
                binds.append(bindparam("parent_ids", type_=ARRAY(String)))
            if min_chunk_index is not None:
                clauses.append("chunk_index >= :min_chunk_index")
                params["min_chunk_index"] = min_chunk_index
            if scope is not None or version is not None or kind is not None:
                family_ids = self._family_ids(
                    session, collection, scope=scope, version=version, kind=kind
                )
                if not family_ids:
                    return 0
                clauses.append("family_id = ANY(:family_ids)")
                params["family_ids"] = family_ids

            statement = text(
                f"DELETE FROM vector_documents WHERE {' AND '.join(clauses)}"  # noqa: S608 - literal clauses
            )
            if binds:
                statement = statement.bindparams(*binds)
            result = session.execute(statement, params)
            session.commit()
            return result.rowcount

    def prune_missing(
        self, collection: str, family: Family, keep_parent_ids: Sequence[str]
    ) -> int:
        with self._session_factory() as session:
            self._require(session, collection)
            result = session.execute(
                _PRUNE_MISSING,
                {
                    "collection": collection,
                    "scope": family.scope,
                    "version": family.version,
                    "kind": family.kind,
                    "keep": list(keep_parent_ids),
                },
            )
            session.commit()
            return result.rowcount
```

- [ ] **Step 4: Export the new name**

In `src/autobots_devtools_shared_lib/common/services/vector/__init__.py`, add:

```python
from autobots_devtools_shared_lib.common.services.vector.pg_store import PgVectorStore
```

and add `"PgVectorStore"` to `__all__` in sorted position.

- [ ] **Step 5: Run the integration tests to verify they pass**

```bash
export VECTOR_TEST_DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5433/postgres"
../.venv/bin/pytest tests/integration/test_pgvector_store.py -v --no-cov
```

Expected: PASS, 20 tests. If `family_ids` binding errors with an array-type
mismatch, simplify the bind to a plain
`bindparam("family_ids", type_=ARRAY(Integer))` (import `Integer` from
`sqlalchemy`) — family ids are `int`, not `str`, and that is the only place the
draft above guesses at the array element type.

- [ ] **Step 6: Confirm the unit suite still passes without Postgres**

```bash
unset VECTOR_TEST_DATABASE_URL
../.venv/bin/pytest tests/unit -q --no-cov
```

Expected: PASS, no skips introduced in `tests/unit`.

- [ ] **Step 7: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/services/vector tests/integration
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/services/vector tests/integration
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/services/vector
git add src/autobots_devtools_shared_lib/common/services/vector tests/integration
git commit -m "feat(vector): PgVectorStore over SQLAlchemy and pgvector"
```

- [ ] **Step 8: Tear down the test database**

```bash
docker rm -f pgvector-test
```

---

### Task 9: `semantic_search` agent tool

**Files:**
- Create: `src/autobots_devtools_shared_lib/common/tools/vector_tools.py`
- Test: `tests/unit/vector/test_vector_tools.py`

**Interfaces:**
- Consumes: `get_semantic_search_service()` (Task 6), `ScoredDoc` (Task 1).
- Produces:

```python
def make_semantic_search_tool(
    collection: str,
    *,
    state_cls: type = Dynagent,
    scope: str | None = None,
    version: str | None = None,
    kind: str | None = None,
    default_top_k: int = 5,
    max_top_k: int = 20,
) -> Any: ...
```

  Returns one `@tool`-wrapped callable named `semantic_search`. The LLM sees only
  `query`, `kind`, and `top_k`; `collection`, `scope`, and `version` are bound at
  registration, so an agent cannot search a corpus it was not given.

Follows the `make_context_tools` factory idiom in
`common/tools/context_tools.py` — including the
`__annotations__["runtime"] = ToolRuntime[None, state_cls]` rebinding, which is
how a domain's state class reaches the tool signature without the LLM seeing it.
The tool is **not** added to `get_default_tools()`: a shared-lib default would
call `get_semantic_search_service()` in every domain, including the ones that
never wire it. Domains opt in through `register_usecase_tools`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/test_vector_tools.py`:

```python
# ABOUTME: Unit tests for the semantic_search dynagent tool.
# ABOUTME: Config-bound collection/scope must not be reachable from the LLM's arguments.

import json

import pytest

from autobots_devtools_shared_lib.common.services.vector import (
    IndexDoc,
    InMemoryVectorStore,
    SemanticSearchService,
    reset_semantic_search_service,
    set_semantic_search_service,
)
from autobots_devtools_shared_lib.common.tools.vector_tools import make_semantic_search_tool

COLLECTION = "kg-nodes"


@pytest.fixture
def wired_service(embedder):
    from tests.unit.vector.conftest import FixedChunker

    service = SemanticSearchService(
        InMemoryVectorStore(), embedder=embedder, chunker=FixedChunker()
    )
    service.index(
        COLLECTION,
        [
            IndexDoc(
                parent_id="rules",
                content="deposit account closure rules",
                scope="app",
                version="develop",
                kind="LPU",
            ),
            IndexDoc(
                parent_id="invoice",
                content="invoice payment terms",
                scope="app",
                version="develop",
                kind="LPU",
            ),
            IndexDoc(
                parent_id="dto",
                content="deposit account dto",
                scope="app",
                version="develop",
                kind="Model--DTO",
            ),
        ],
    )
    set_semantic_search_service(service)
    yield service
    reset_semantic_search_service()


def test_tool_is_named_semantic_search():
    tool = make_semantic_search_tool(COLLECTION)

    assert tool.name == "semantic_search"
    assert "semantic" in tool.description.lower()


def test_the_llm_sees_only_query_kind_and_top_k():
    tool = make_semantic_search_tool(COLLECTION, scope="app", version="develop")

    properties = tool.args_schema.model_json_schema()["properties"]

    assert set(properties) == {"query", "kind", "top_k"}


def test_invoking_the_tool_returns_scored_hits_as_json(wired_service):
    tool = make_semantic_search_tool(COLLECTION)

    payload = json.loads(tool.invoke({"query": "deposit account closure"}))

    assert payload["collection"] == COLLECTION
    assert payload["results"][0]["parent_id"] == "rules"
    assert set(payload["results"][0]) == {
        "parent_id",
        "chunk_index",
        "content",
        "score",
        "scope",
        "version",
        "kind",
        "metadata",
    }


def test_bound_scope_and_version_are_applied(wired_service):
    tool = make_semantic_search_tool(COLLECTION, scope="absent-app")

    payload = json.loads(tool.invoke({"query": "deposit"}))

    assert payload["results"] == []


def test_the_llm_can_narrow_by_kind(wired_service):
    tool = make_semantic_search_tool(COLLECTION, scope="app", version="develop")

    payload = json.loads(tool.invoke({"query": "deposit account", "kind": "Model--DTO"}))

    assert [r["parent_id"] for r in payload["results"]] == ["dto"]


def test_bound_kind_wins_when_the_tool_is_pinned(wired_service):
    tool = make_semantic_search_tool(COLLECTION, kind="LPU")

    payload = json.loads(tool.invoke({"query": "deposit account", "kind": "Model--DTO"}))

    assert {r["kind"] for r in payload["results"]} == {"LPU"}


def test_top_k_defaults_and_is_clamped(wired_service):
    tool = make_semantic_search_tool(COLLECTION, default_top_k=1, max_top_k=2)

    default_payload = json.loads(tool.invoke({"query": "deposit"}))
    clamped_payload = json.loads(tool.invoke({"query": "deposit", "top_k": 99}))

    assert len(default_payload["results"]) == 1
    assert len(clamped_payload["results"]) == 2


def test_an_unknown_collection_returns_an_error_payload_not_an_exception(wired_service):
    tool = make_semantic_search_tool("never-indexed")

    payload = json.loads(tool.invoke({"query": "deposit"}))

    assert payload["results"] == []
    assert "never-indexed" in payload["error"]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_vector_tools.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: ...common.tools.vector_tools`.

- [ ] **Step 3: Write `vector_tools.py`**

Create `src/autobots_devtools_shared_lib/common/tools/vector_tools.py`:

```python
# ABOUTME: The semantic_search dynagent tool, built per-collection at registration time.
# ABOUTME: Corpus and family scope are bound in config; the LLM only supplies the query.

from __future__ import annotations

import json
from typing import Any

from langchain.tools import ToolRuntime, tool

from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger
from autobots_devtools_shared_lib.common.services.vector.errors import VectorStoreError
from autobots_devtools_shared_lib.common.services.vector.factory import (
    get_semantic_search_service,
)
from autobots_devtools_shared_lib.dynagent.models.state import Dynagent

logger = get_logger(__name__)


def make_semantic_search_tool(
    collection: str,
    *,
    state_cls: type = Dynagent,
    scope: str | None = None,
    version: str | None = None,
    kind: str | None = None,
    default_top_k: int = 5,
    max_top_k: int = 20,
) -> Any:
    """Return a `semantic_search` tool bound to one collection.

    Args:
        collection: Corpus to search, e.g. "kg-nodes".
        state_cls:  Agent state TypedDict used to type the injected runtime
                    parameter. Invisible to the LLM.
        scope:      Fixed component/repo filter, or None to search every scope.
        version:    Fixed branch/version filter, or None for every version.
        kind:       Fixed document-type filter. When set, it overrides whatever
                    the LLM passes — a pinned tool stays pinned.
        default_top_k: Hits returned when the LLM does not ask for a count.
        max_top_k:  Ceiling on the LLM's requested count, so one call cannot
                    flood the context window.
    """
    # The inner parameter must stay named `kind` (that name is what the LLM sees),
    # so the bound value is captured here under a distinct name first.
    bound_kind = kind

    def semantic_search(
        runtime: ToolRuntime[None, Any],  # noqa: ARG001 - required by the tool protocol
        query: str,
        kind: str | None = None,
        top_k: int | None = None,
    ) -> str:
        """Search the indexed corpus semantically and return the closest passages.

        Use natural language describing what you are looking for, not keywords.
        Optionally narrow by `kind` (document type). Results are ranked by
        similarity, highest first, and each carries the id of the document it
        came from.
        """
        resolved_kind = bound_kind if bound_kind is not None else kind
        resolved_top_k = min(top_k or default_top_k, max_top_k)
        try:
            hits = get_semantic_search_service().search(
                collection,
                query,
                top_k=resolved_top_k,
                scope=scope,
                version=version,
                kind=resolved_kind,
            )
        except VectorStoreError as exc:
            logger.warning("semantic_search failed for collection %s: %s", collection, exc)
            return json.dumps(
                {"collection": collection, "query": query, "results": [], "error": str(exc)}
            )

        return json.dumps(
            {
                "collection": collection,
                "query": query,
                "results": [
                    {
                        "parent_id": hit.parent_id,
                        "chunk_index": hit.chunk_index,
                        "content": hit.content,
                        "score": round(hit.score, 4),
                        "scope": hit.scope,
                        "version": hit.version,
                        "kind": hit.kind,
                        "metadata": dict(hit.metadata),
                    }
                    for hit in hits
                ],
            }
        )

    semantic_search.__annotations__["runtime"] = ToolRuntime[None, state_cls]
    return tool(semantic_search)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector/test_vector_tools.py -v --no-cov
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/common/tools/vector_tools.py tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/common/tools/vector_tools.py tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/common/tools/vector_tools.py
git add src/autobots_devtools_shared_lib/common/tools/vector_tools.py tests/unit/vector
git commit -m "feat(vector): semantic_search dynagent tool factory"
```

---

### Task 10: FastAPI router

**Files:**
- Create: `src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py`
- Test: `tests/unit/vector/test_router.py`

**Interfaces:**
- Consumes: `SemanticSearchService` (Task 5), `get_semantic_search_service` (Task 6), the error types (Task 1).
- Produces:
  - `build_vector_router(service_provider: Callable[[], SemanticSearchService] = get_semantic_search_service) -> APIRouter` — prefix `/vector`, tag `vector`.
  - `register_vector_exception_handlers(app: FastAPI) -> None` — `CollectionNotFoundError` → 404, `EmbeddingMismatchError` → 409, `VectorConfigError` → 503.

**Two constraints that are not negotiable:**

1. Every handler is a plain `def`, **never** `async def`. FastAPI runs sync
   handlers in its threadpool; the DB and embedding calls are blocking, and an
   `async def` handler would stall the event loop for the whole process. This
   intentionally diverges from `resources/threads.py`, whose store Protocol is
   async.
2. The router carries **no auth**. Domains mount it behind their own auth
   middleware. Say so in the router docstring so nobody assumes otherwise.

`build_vector_router` is deliberately **not** added to `build_resource_router` in
`dynagent/api/router.py` — that router is mounted by domains with no vector
service, and including it would make every one of them resolve a singleton they
never set.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/vector/test_router.py`:

```python
# ABOUTME: TestClient coverage for the /vector router against a real in-memory service.
# ABOUTME: Covers search, index (with prune), delete (with drop), describe, and error mapping.

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autobots_devtools_shared_lib.common.services.vector import (
    InMemoryVectorStore,
    SemanticSearchService,
)
from autobots_devtools_shared_lib.dynagent.api.resources.vector import (
    build_vector_router,
    register_vector_exception_handlers,
)

COLLECTION = "kg-nodes"


@pytest.fixture
def service(embedder):
    from tests.unit.vector.conftest import FixedChunker

    return SemanticSearchService(
        InMemoryVectorStore(), embedder=embedder, chunker=FixedChunker()
    )


@pytest.fixture
def client(service):
    app = FastAPI()
    register_vector_exception_handlers(app)
    app.include_router(build_vector_router(service_provider=lambda: service))
    return TestClient(app)


def _index(client, documents, prune=False):
    return client.post(
        f"/vector/{COLLECTION}/documents",
        json={"documents": documents, "prune": prune},
    )


def test_every_route_handler_is_synchronous():
    import inspect

    router = build_vector_router()

    assert not any(inspect.iscoroutinefunction(route.endpoint) for route in router.routes)


def test_index_documents(client):
    response = _index(client, [{"parent_id": "a", "content": "deposit account"}])

    assert response.status_code == 200
    assert response.json() == {
        "chunks_written": 1,
        "chunks_skipped": 0,
        "chunks_pruned": 0,
        "documents_pruned": 0,
    }


def test_reindexing_identical_documents_skips_them(client):
    documents = [{"parent_id": "a", "content": "deposit account"}]
    _index(client, documents)

    body = _index(client, documents).json()

    assert (body["chunks_written"], body["chunks_skipped"]) == (0, 1)


def test_index_with_prune_removes_departed_documents(client):
    _index(
        client,
        [
            {"parent_id": "a", "content": "deposit", "scope": "app", "kind": "LPU"},
            {"parent_id": "b", "content": "account", "scope": "app", "kind": "LPU"},
        ],
    )

    body = _index(
        client,
        [{"parent_id": "a", "content": "deposit", "scope": "app", "kind": "LPU"}],
        prune=True,
    ).json()

    assert body["documents_pruned"] == 1


def test_index_rejects_an_empty_document_list(client):
    response = client.post(f"/vector/{COLLECTION}/documents", json={"documents": []})

    assert response.status_code == 422


def test_search(client):
    _index(
        client,
        [
            {"parent_id": "rules", "content": "deposit account closure rules"},
            {"parent_id": "invoice", "content": "invoice payment terms"},
        ],
    )

    response = client.post(
        f"/vector/{COLLECTION}/search", json={"query": "deposit account closure", "top_k": 2}
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["parent_id"] for r in results] == ["rules", "invoice"]
    assert results[0]["score"] > results[1]["score"]


def test_search_with_filters(client):
    _index(
        client,
        [
            {
                "parent_id": "a",
                "content": "deposit",
                "scope": "app",
                "version": "develop",
                "kind": "LPU",
                "metadata": {"tier": 1},
            },
            {
                "parent_id": "b",
                "content": "deposit",
                "scope": "app",
                "version": "develop",
                "kind": "DTO",
                "metadata": {"tier": 2},
            },
        ],
    )

    response = client.post(
        f"/vector/{COLLECTION}/search",
        json={
            "query": "deposit",
            "scope": "app",
            "version": "develop",
            "kind": "LPU",
            "metadata_filter": {"tier": 1},
        },
    )

    assert [r["parent_id"] for r in response.json()["results"]] == ["a"]


def test_search_on_an_unknown_collection_is_404(client):
    response = client.post("/vector/never-indexed/search", json={"query": "deposit"})

    assert response.status_code == 404
    assert "never-indexed" in response.json()["detail"]


def test_describe(client):
    _index(client, [{"parent_id": "a", "content": "deposit|account"}])

    response = client.get(f"/vector/{COLLECTION}")

    assert response.status_code == 200
    assert response.json() == {
        "name": COLLECTION,
        "model": "fake-embedding",
        "dim": 8,
        "document_count": 2,
    }


def test_describe_on_an_unknown_collection_is_404(client):
    assert client.get("/vector/never-indexed").status_code == 404


def test_delete_by_parent_ids(client):
    _index(
        client,
        [
            {"parent_id": "a", "content": "deposit"},
            {"parent_id": "b", "content": "account"},
        ],
    )

    response = client.delete(f"/vector/{COLLECTION}?parent_ids=a")

    assert response.status_code == 200
    assert response.json() == {"deleted": 1, "dropped": False}


def test_delete_by_scope_and_version(client):
    _index(
        client,
        [
            {"parent_id": "a", "content": "deposit", "scope": "app", "version": "v1"},
            {"parent_id": "b", "content": "account", "scope": "app", "version": "v2"},
        ],
    )

    response = client.delete(f"/vector/{COLLECTION}?scope=app&version=v1")

    assert response.json()["deleted"] == 1


def test_delete_without_criteria_is_422(client):
    _index(client, [{"parent_id": "a", "content": "deposit"}])

    response = client.delete(f"/vector/{COLLECTION}")

    assert response.status_code == 422


def test_delete_with_drop_removes_the_collection(client):
    _index(client, [{"parent_id": "a", "content": "deposit"}])

    response = client.delete(f"/vector/{COLLECTION}?drop=true")

    assert response.json() == {"deleted": 0, "dropped": True}
    assert client.get(f"/vector/{COLLECTION}").status_code == 404


def test_embedding_mismatch_is_409(client, service):
    _index(client, [{"parent_id": "a", "content": "deposit"}])
    service._verified.clear()
    service._embedder.model = "text-embedding-3-large"

    response = client.post(f"/vector/{COLLECTION}/search", json={"query": "deposit"})

    assert response.status_code == 409
    assert "drop_collection" in response.json()["detail"]


def test_an_unwired_service_is_503():
    from autobots_devtools_shared_lib.common.services.vector import (
        reset_semantic_search_service,
    )

    reset_semantic_search_service()
    app = FastAPI()
    register_vector_exception_handlers(app)
    app.include_router(build_vector_router())

    response = TestClient(app).get(f"/vector/{COLLECTION}")

    assert response.status_code == 503
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
../.venv/bin/pytest tests/unit/vector/test_router.py -v --no-cov
```

Expected: FAIL with `ModuleNotFoundError: ...api.resources.vector`.

- [ ] **Step 3: Write `resources/vector.py`**

Create `src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py`:

```python
# ABOUTME: /vector router — search, index, delete, and describe over a collection.
# ABOUTME: Handlers are sync on purpose so FastAPI runs blocking DB/embedding work off-loop.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from autobots_devtools_shared_lib.common.services.vector.errors import (
    CollectionNotFoundError,
    EmbeddingMismatchError,
    VectorConfigError,
)
from autobots_devtools_shared_lib.common.services.vector.factory import (
    get_semantic_search_service,
)
from autobots_devtools_shared_lib.common.services.vector.models import IndexDoc

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI, Request

    from autobots_devtools_shared_lib.common.services.vector.service import (
        SemanticSearchService,
    )


class _DocumentBody(BaseModel):
    parent_id: str = Field(min_length=1)
    content: str
    scope: str | None = None
    version: str | None = None
    kind: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class _IndexBody(BaseModel):
    documents: list[_DocumentBody] = Field(min_length=1)
    prune: bool = False


class _SearchBody(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    scope: str | None = None
    version: str | None = None
    kind: str | None = None
    metadata_filter: dict[str, Any] | None = None


def register_vector_exception_handlers(app: FastAPI) -> None:
    """Map vector domain errors to typed JSON HTTP responses."""

    @app.exception_handler(CollectionNotFoundError)
    async def _not_found(_request: Request, exc: CollectionNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"collection not found: {exc}"})

    @app.exception_handler(EmbeddingMismatchError)
    async def _conflict(_request: Request, exc: EmbeddingMismatchError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(VectorConfigError)
    async def _unavailable(_request: Request, exc: VectorConfigError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})


def build_vector_router(
    service_provider: Callable[[], SemanticSearchService] = get_semantic_search_service,
) -> APIRouter:
    """Build the /vector router.

    Every handler is a plain `def`: FastAPI runs sync handlers in its threadpool,
    and the DB and embedding calls behind them are blocking. Declaring them
    `async def` would stall the event loop for the whole process.

    The router carries no authentication. Domains are responsible for mounting it
    behind their own auth middleware.
    """
    router = APIRouter(prefix="/vector", tags=["vector"])

    @router.post("/{collection}/search")
    def search(collection: str, body: _SearchBody) -> dict[str, Any]:
        hits = service_provider().search(
            collection,
            body.query,
            top_k=body.top_k,
            scope=body.scope,
            version=body.version,
            kind=body.kind,
            metadata_filter=body.metadata_filter,
        )
        return {
            "collection": collection,
            "query": body.query,
            "results": [
                {
                    "doc_id": hit.doc_id,
                    "parent_id": hit.parent_id,
                    "chunk_index": hit.chunk_index,
                    "content": hit.content,
                    "score": hit.score,
                    "scope": hit.scope,
                    "version": hit.version,
                    "kind": hit.kind,
                    "metadata": dict(hit.metadata),
                }
                for hit in hits
            ],
        }

    @router.post("/{collection}/documents")
    def index_documents(collection: str, body: _IndexBody) -> dict[str, int]:
        result = service_provider().index(
            collection,
            [
                IndexDoc(
                    parent_id=document.parent_id,
                    content=document.content,
                    scope=document.scope,
                    version=document.version,
                    kind=document.kind,
                    metadata=document.metadata,
                )
                for document in body.documents
            ],
            prune=body.prune,
        )
        return {
            "chunks_written": result.chunks_written,
            "chunks_skipped": result.chunks_skipped,
            "chunks_pruned": result.chunks_pruned,
            "documents_pruned": result.documents_pruned,
        }

    @router.delete("/{collection}")
    def delete_documents(
        collection: str,
        ids: list[str] | None = Query(default=None),
        parent_ids: list[str] | None = Query(default=None),
        scope: str | None = None,
        version: str | None = None,
        kind: str | None = None,
        drop: bool = False,
    ) -> dict[str, Any]:
        service = service_provider()
        if drop:
            service.drop_collection(collection)
            return {"deleted": 0, "dropped": True}
        if not any((ids, parent_ids, scope, version, kind)):
            raise HTTPException(
                status_code=422,
                detail=(
                    "provide ids, parent_ids, scope, version, or kind — "
                    "use ?drop=true to remove the whole collection"
                ),
            )
        deleted = service.delete(
            collection,
            ids,
            scope=scope,
            version=version,
            kind=kind,
            parent_ids=parent_ids,
        )
        return {"deleted": deleted, "dropped": False}

    @router.get("/{collection}")
    def describe(collection: str) -> dict[str, Any]:
        info = service_provider().describe(collection)
        if info is None:
            raise CollectionNotFoundError(collection)
        return {
            "name": info.name,
            "model": info.model,
            "dim": info.dim,
            "document_count": info.document_count,
        }

    return router
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
../.venv/bin/pytest tests/unit/vector/test_router.py -v --no-cov
```

Expected: PASS, 16 tests.

- [ ] **Step 5: Lint, type-check, and commit**

```bash
../.venv/bin/ruff format src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py tests/unit/vector
../.venv/bin/ruff check --fix src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py tests/unit/vector
../.venv/bin/pyright src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py
git add src/autobots_devtools_shared_lib/dynagent/api/resources/vector.py tests/unit/vector
git commit -m "feat(vector): FastAPI router for search, index, delete, and describe"
```

---

### Task 11: Public exports, documentation, and full-suite verification

**Files:**
- Modify: `src/autobots_devtools_shared_lib/common/services/__init__.py`
- Create: `src/autobots_devtools_shared_lib/common/services/vector/README.md`
- Modify: `CONTEXT.md`
- Test: `tests/unit/vector/test_factory.py`

**Interfaces:**
- Consumes: every public name from Tasks 1–10.
- Produces: the documented integration path. Nothing later depends on this task.

- [ ] **Step 1: Write the failing export test**

Append to `tests/unit/vector/test_factory.py`:

```python
def test_vector_public_api_is_reachable_from_common_services():
    import autobots_devtools_shared_lib.common.services as services

    for name in (
        "SemanticSearchService",
        "PgVectorStore",
        "InMemoryVectorStore",
        "VectorStore",
        "IndexDoc",
        "ScoredDoc",
        "Family",
        "EmbeddingMismatchError",
        "CollectionNotFoundError",
        "get_semantic_search_service",
        "set_semantic_search_service",
        "vector_schema_sql",
    ):
        assert name in services.__all__
        assert getattr(services, name) is not None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
../.venv/bin/pytest tests/unit/vector/test_factory.py -k public_api -v --no-cov
```

Expected: FAIL with `AssertionError` on `"SemanticSearchService" in services.__all__`.

- [ ] **Step 3: Re-export from `common/services/__init__.py`**

In `src/autobots_devtools_shared_lib/common/services/__init__.py`, add a bullet to
the module docstring:

```
* SemanticSearchService - corpus-agnostic embedding and semantic search.
```

then add the import block after the existing `context` import:

```python
from autobots_devtools_shared_lib.common.services.vector import (
    CollectionInfo,
    CollectionNotFoundError,
    EmbeddingMismatchError,
    Family,
    InMemoryVectorStore,
    IndexDoc,
    IndexResult,
    PgVectorStore,
    ScoredDoc,
    SemanticSearchService,
    VectorStore,
    get_semantic_search_service,
    set_semantic_search_service,
    vector_schema_sql,
)
```

and extend `__all__` with those fourteen names, keeping it sorted.

- [ ] **Step 4: Write the README**

Create `src/autobots_devtools_shared_lib/common/services/vector/README.md`:

````markdown
# Semantic search: SemanticSearchService, VectorStore, and the pgvector schema

Corpus-agnostic embedding and retrieval. A domain hands over **whole documents**;
this package chunks, embeds, stores, and searches them. Callers never chunk and
never embed.

## Requirements

- PostgreSQL **≥ 15** (`UNIQUE NULLS NOT DISTINCT`)
- pgvector **≥ 0.8** (iterative index scans — older versions under-return on
  heavily filtered ANN queries)
- `OPENAI_API_KEY` in the environment

## Wiring it up (once, at server startup)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autobots_devtools_shared_lib.common.services import (
    PgVectorStore,
    SemanticSearchService,
    set_semantic_search_service,
)

engine = create_engine(settings.database_url, pool_pre_ping=True)
session_factory = sessionmaker(bind=engine, expire_on_commit=False)
set_semantic_search_service(SemanticSearchService(PgVectorStore(session_factory)))
```

shared-lib never owns connection config — the domain supplies the sessionmaker.
There is no fallback: calling `get_semantic_search_service()` before
`set_semantic_search_service()` raises `VectorConfigError` rather than silently
using an in-memory store.

## Applying the schema

`vector_schema_sql()` returns idempotent DDL. Apply it through your domain's own
migration pipeline; shared-lib ships the SQL but never runs it.

```python
from autobots_devtools_shared_lib.common.services import vector_schema_sql
```

## Indexing

```python
from autobots_devtools_shared_lib.common.services import IndexDoc

service.index(
    "kg-nodes",
    [
        IndexDoc(
            parent_id="fbp-product-deposit-app--develop--Model--DTO--Account",
            content="Account\n\nHolds the customer's deposit balance...",
            scope="fbp-product-deposit-app",
            version="develop",
            kind="Model--DTO",
            metadata={"path": "nodes/Account.json"},
        )
    ],
    prune=True,
)
```

`index()` is idempotent end to end:

- **Unchanged content costs nothing** — chunks are hashed and diffed in the
  store, so a re-index with identical text makes zero embedding calls and zero
  writes.
- **Shrunk documents lose their tail** — if a document re-chunks to fewer pieces,
  the leftover chunks are always deleted.
- **`prune=True` clears departed documents** — rows in the batch's families whose
  `parent_id` was absent from the batch are removed. This makes "re-index this
  snapshot" one call; do *not* delete-then-reindex, which throws away the
  hash-skip.

## Searching

```python
hits = service.search(
    "kg-nodes",
    "deposit account closure rules",
    scope="fbp-product-deposit-app",
    version="develop",
    kind="LPU",
    top_k=10,
)
```

Hits are **chunks**, carrying `parent_id` and `chunk_index`. Regrouping them into
documents is the caller's concern — the service deliberately does not dedup or
group.

`score` is **cosine similarity**: higher is better, range `[-1, 1]`.

`metadata_filter` is top-level key containment with **scalar values only**
(`{"tier": 1}`). A list or dict value raises `ValueError`.

## The three filter axes

`scope`, `version`, and `kind` are stored in `vector_document_family`, not in
`metadata`. Searches resolve filter values to family ids first, so the hot path
is integer equality — which filtered HNSW handles far better than three text
predicates, and which the planner has real statistics for. Use `metadata` only
for the corpus-specific long tail.

| Corpus | `scope` | `version` | `kind` |
|---|---|---|---|
| KG nodes | component/repo | branch | node type |
| KBE articles | product | version | article type |
| Designer sources | repo | iteration | source type |

## Agent tool

```python
from autobots_devtools_shared_lib.common.tools.vector_tools import make_semantic_search_tool
from autobots_devtools_shared_lib.dynagent import register_usecase_tools

register_usecase_tools([
    make_semantic_search_tool("kg-nodes", scope="fbp-product-deposit-app", version="develop"),
])
```

The collection and any bound `scope`/`version` are fixed at registration; the LLM
supplies only `query`, an optional `kind`, and an optional `top_k`.

## HTTP routes

```python
from autobots_devtools_shared_lib.dynagent.api.resources.vector import (
    build_vector_router,
    register_vector_exception_handlers,
)

register_vector_exception_handlers(app)
app.include_router(build_vector_router())
```

| Route | Purpose |
|---|---|
| `POST /vector/{collection}/search` | Query + optional filters |
| `POST /vector/{collection}/documents` | Index documents (optional `prune`) |
| `DELETE /vector/{collection}` | By `ids`, `parent_ids`, or `scope`/`version`/`kind`; `?drop=true` removes the collection |
| `GET /vector/{collection}` | `describe()` |

**These routes carry no authentication.** Mount them behind your domain's auth
middleware.

## Operations

**Switching embedding models.** Vectors from two models are not comparable, so
the service refuses to mix them: any mismatch between the configured model/dim
and the collection's registry row raises `EmbeddingMismatchError`. The recovery
path is `drop_collection(name)` followed by a full re-index.

**Changing `embedding_dim`** requires a schema migration — the column is
`vector(1536)`. The registry records dim per collection so a future second
dimension has known escape hatches (partial cast indexes, `halfvec`), but none
are built today.

**`top_k` above `hnsw.ef_search`** (default 40) silently truncates results. Raise
`ef_search` on the session before issuing large-`top_k` queries.

**Heavy filters plus an ANN index can under-return** on pgvector < 0.8. Pin 0.8+,
where iterative index scans fix it.

## Testing against this package

Use `InMemoryVectorStore` with a fake embedder. Its semantics are identical to
`PgVectorStore` by construction — the upsert partition, the wildcard-vs-exact
null rules, cosine scoring, and metadata containment all match — so unit tests
against the fake predict Postgres behaviour. See `tests/unit/vector/conftest.py`.
````

- [ ] **Step 5: Add the vocabulary to `CONTEXT.md`**

Append a section to `CONTEXT.md`, matching the existing `**Term**:` / `_Avoid_:`
format:

```markdown
### Semantic search

**Collection**:
A named corpus of indexed documents sharing one embedding model and dimension, e.g. `kg-nodes`. Registered in `vector_collections`; the unit of drop-and-reindex.
_Avoid_: index, namespace, table

**Family**:
The `(scope, version, kind)` triple a document belongs to. Stored as a row in `vector_document_family` so searches filter on an integer id, not three text predicates.
_Avoid_: partition, bucket, tag

**Parent Id**:
The caller's stable id for a whole source document. Survives re-indexing and ties chunks back to their source.
_Avoid_: document id, key

**Chunk**:
One token-sized slice of a document's content — the unit that is embedded, stored, and returned by search. Identified by `{parent_id}#{chunk_index}`.
_Avoid_: fragment, passage, segment

**Hash-Skip**:
Leaving a stored chunk untouched because its `content_hash` is unchanged. What makes re-indexing cost zero embedding calls.
_Avoid_: cache hit, dedup

**Chunk-Tail Prune**:
Deleting chunks past the new end of a document that re-chunked to fewer pieces. Always applied.
_Avoid_: truncate, cleanup

**Family Prune**:
Deleting documents in the batch's families whose `parent_id` was absent from the batch. Opt-in via `prune=True`; makes snapshot re-indexing idempotent.
_Avoid_: sync, reconcile
```

- [ ] **Step 6: Run the full unit suite with coverage**

```bash
unset VECTOR_TEST_DATABASE_URL
../.venv/bin/pytest tests/unit -v
```

Expected: PASS, with no pre-existing test broken. Report the pass count and the
coverage figure for `common/services/vector`.

- [ ] **Step 7: Run every check**

```bash
../.venv/bin/ruff format --check src tests
../.venv/bin/ruff check src tests
../.venv/bin/pyright src tests
```

Expected: all three clean. If `ruff format --check` reports files, run
`../.venv/bin/ruff format src tests` and re-run.

- [ ] **Step 8: Run the integration suite once more against a live database**

```bash
docker run -d --name pgvector-test -e POSTGRES_PASSWORD=postgres -p 5433:5432 pgvector/pgvector:pg16
export VECTOR_TEST_DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5433/postgres"
../.venv/bin/pytest tests/integration/test_pgvector_store.py -v --no-cov
docker rm -f pgvector-test
```

Expected: PASS, 20 tests. State the real result — a skip is not a pass.

- [ ] **Step 9: Commit**

```bash
git add src/autobots_devtools_shared_lib/common/services CONTEXT.md tests/unit/vector
git commit -m "docs(vector): public exports, integration README, and vocabulary"
```

---

### Task 12: Version bump and integration handoff

**Files:**
- Modify: `pyproject.toml` (version field only)

**Interfaces:**
- Consumes: a green Task 11.
- Produces: nothing importable. This task ends the plan.

shared-lib is a published package (see `PUBLISHING.md`) and three domains consume
it through local path dependencies. This change is purely additive — no existing
symbol changes signature — so it takes a prerelease bump on the current beta line,
not a minor. A consuming domain needs *some* version to pin against; leaving
`0.11.0b3` in place would ship two different libraries under one version.

- [ ] **Step 1: Bump the version**

```bash
cd /Users/pralhad/work/src/ws-autobots/autobots-devtools-shared-lib
source ../.venv/bin/activate
poetry version prerelease
poetry version -s
```

Expected: `0.11.0b4`. If the current version has moved on since this plan was
written, take whatever `poetry version prerelease` produces — do not hand-edit the
field.

- [ ] **Step 2: Verify the lock still checks out**

Changing the version rewrites `pyproject.toml`, which re-triggers
`poetry-lock-check` on commit.

```bash
poetry check --lock
```

Expected: exits 0. If it reports the lock is stale, run `poetry lock` and stage
the result with the commit below.

- [ ] **Step 3: Run every check one final time**

```bash
make all-checks
```

Expected: `check-format`, `type-check`, and `test` all clean. This is the same
gate the pre-commit hooks apply, run once against the finished branch.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to $(poetry version -s)"
```

- [ ] **Step 5: Report and stop**

```bash
git log --oneline main..HEAD
```

Expected: 13 commits (Task 0's branch step produces none of its own; Tasks 1–12
produce one each, and Task 0 produces one).

Summarize for the reviewer:

- Total tests added and the coverage figure for `common/services/vector`.
- Whether the integration suite **ran against a real Postgres or skipped** — a
  skip is not a pass, and must be reported as a gap.
- The new version.
- The two follow-ups this plan deliberately leaves to the consuming domains:
  1. Applying `vector_schema_sql()` through the domain's migration pipeline.
  2. Calling `set_semantic_search_service()` at domain startup — nothing in
     shared-lib does this, and every route and tool fails with
     `VectorConfigError` until a domain does.

**Do not merge, push, or open a PR.** Integration is the user's decision — see
`superpowers:finishing-a-development-branch`.

---

## Self-Review

Checked after writing, against
`docs/superpowers/specs/2026-07-22-pgvector-semantic-search-design.md`.

**Spec coverage.** Every in-scope item maps to a task: chunking (2), embedding
generation (3), pgvector storage (7, 8), similarity search (4, 5, 8), deletion
(4, 5, 8), pruning of stale documents and chunks (5), collection registry (4, 7,
8), dimension-mismatch guard (5), agent tool (9), FastAPI router (10), in-memory
fake (4). Settings, dependencies, and the SQL migration land in 0 and 7. Both
error types, the retry-with-backoff path, the filtered-HNSW and `ef_search`
caveats, and the KG use-case mapping are documented in 11. The out-of-scope list
(document loading, hybrid search, re-ranking, result dedup, per-collection
dimensions, async SQLAlchemy) is absent from every task, as intended.

**Gaps found and closed.** The spec's Protocol sketch could not express its own
requirements; the three additions and the two-statement upsert are recorded in
"Deviations from the spec" above rather than left for the implementer to
rediscover. `VectorConfigError` was not in the spec's error list — the singleton
needs it, so Task 6 adds it.

**Type consistency.** `VectorDoc.doc_id` is `"{parent_id}#{chunk_index}"`
everywhere. `delete()` returns `int` and takes `min_chunk_index` in the Protocol,
both stores, and the service. `prune_missing(collection, family, keep_parent_ids)`
has one signature throughout. `IndexResult`'s four field names are identical in
`models.py`, the service, the router response, and every test. `Embedder` exposes
`model`/`dim` as attributes (not properties) so `FakeEmbedder`'s class attributes
satisfy it, and it is not `@runtime_checkable` — the one Protocol here with
non-method members.

**Known soft spot.** Task 8, Step 5 flags the single place the draft SQL guesses:
the `family_ids` array bind element type. The fix is spelled out inline.

**Second review pass, against the repo's tooling rather than the spec.** Four
things the first pass missed, all now fixed:

- Task 0 added five dependencies to `pyproject.toml` and committed without
  re-locking. `poetry check --lock` currently passes, and `poetry-lock-check` is
  a pre-commit hook gated on `pyproject.toml` — so that commit would have failed.
  Task 0 now runs `poetry lock` / `poetry install` (not `pip install`, which
  leaves the lock untouched; `poetry.toml` sets `virtualenvs.create = false`, so
  poetry installs into the shared venv) and stages `poetry.lock`.
- No version bump. shared-lib is published and consumed by three domains through
  path deps; shipping this under the existing `0.11.0b3` would put two different
  libraries behind one version. Task 12 adds `poetry version prerelease`.
- No closing integration step, and nothing telling the implementer *not* to merge
  or push. Task 12 ends with the commit accounting and an explicit handoff to
  `superpowers:finishing-a-development-branch`, matching the convention in
  `2026-07-17-isolated-history-mode.md`.
- No guidance for a failed task. Global Constraints now says: stop, leave the
  branch alone, report the failing task and step with real output — do not revert
  earlier commits or skip ahead.

**Verified, not assumed.** `from tests.unit.vector.conftest import FixedChunker`
works — `tests/__init__.py` exists and `from tests.conftest import ...` is
established in `tests/integration/`. There is no coverage `fail_under`, so no
coverage gate to satisfy. Task 4's local `store` fixture correctly shadows the
`conftest.py` one added in Task 5; Task 5 now says so explicitly.

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-07-23-pgvector-semantic-search.md`.
