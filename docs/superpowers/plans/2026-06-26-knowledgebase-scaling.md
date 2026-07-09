# Knowledgebase Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove startup-time full knowledge warmup and introduce course-scoped BM25 snapshots so retrieval cost grows with the selected course instead of the whole library.

**Architecture:** Keep Chroma as the dense store, but stop treating BM25 as one global cache rebuilt from `chroma_get_all()`. Add metadata-backed snapshot routing by `course_id`, make retrieval lazily load the right sparse partition on demand, and update UI/API to report readiness instead of blocking startup on a full restore.

**Tech Stack:** Python, Streamlit, FastAPI, pytest, ChromaDB, rank-bm25, SQL-free JSON metadata

---

## File Map

- Create: `tests/knowledge/test_metadata.py`
  - Verifies course-scoped snapshot metadata is recorded and listed correctly.
- Create: `tests/knowledge/test_bm25_index.py`
  - Verifies course-partition snapshot build/load/delete behavior.
- Modify: `src/final_agent/knowledge/metadata.py`
  - Persist BM25 snapshot path and chunk totals per course.
- Modify: `src/final_agent/knowledge/bm25_index.py`
  - Replace one global snapshot path with per-course snapshot helpers and lazy course loading.
- Modify: `src/final_agent/knowledge/builder.py`
  - Rebuild only the affected course partition during ingestion and deletion.
- Modify: `src/final_agent/knowledge/__init__.py`
  - Re-export the new BM25 helpers used by retrieval/UI/API.
- Modify: `src/final_agent/retrieval/hybrid_searcher.py`
  - Ensure sparse retrieval loads the correct course partition before search.
- Modify: `src/final_agent/ui/app.py`
  - Remove blocking startup warmup and show knowledge readiness state.
- Modify: `src/final_agent/api/app.py`
  - Remove blocking startup warmup and make retrieval-side lazy load the source of truth.
- Modify: `tests/retrieval/test_hybrid_searcher.py`
  - Verify hybrid retrieval requests scoped BM25 readiness before sparse search.

## Task 1: Record course-scoped knowledge metadata

**Files:**
- Create: `tests/knowledge/test_metadata.py`
- Modify: `src/final_agent/knowledge/metadata.py`

- [ ] **Step 1: Write the failing metadata tests**

```python
from __future__ import annotations


def test_register_document_tracks_course_snapshot_path(tmp_path):
    from final_agent.knowledge.metadata import list_course_index_info, register_document
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    register_document(
        "doc-a",
        "course-a/lesson.md",
        3,
        settings=settings,
        course_id="course-a",
        bm25_snapshot_path=str(tmp_path / "bm25_course-a.json"),
    )

    info = list_course_index_info(settings)

    assert info["course-a"]["chunk_count"] == 3
    assert info["course-a"]["doc_ids"] == ["doc-a"]
    assert info["course-a"]["bm25_snapshot_path"].endswith("bm25_course-a.json")


def test_remove_document_updates_course_chunk_totals(tmp_path):
    from final_agent.knowledge.metadata import list_course_index_info, register_document, remove_document
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    register_document("doc-a", "a.md", 3, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")
    register_document("doc-b", "b.md", 2, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")

    assert remove_document("doc-a", settings=settings) is True

    info = list_course_index_info(settings)
    assert info["course-a"]["chunk_count"] == 2
    assert info["course-a"]["doc_ids"] == ["doc-b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_metadata.py -v`

Expected: FAIL because `register_document()` does not accept `bm25_snapshot_path` and `list_course_index_info()` does not exist.

- [ ] **Step 3: Write the minimal metadata implementation**

```python
def register_document(
    doc_id: str,
    source_path: str,
    chunk_count: int,
    settings: Settings | None = None,
    *,
    course_id: str = "",
    bm25_snapshot_path: str = "",
) -> None:
    if settings is None:
        settings = load_settings()
    data = _load(settings)
    normalized_course = course_id or "默认课程"
    data["documents"][doc_id] = {
        "source_path": str(source_path),
        "chunk_count": chunk_count,
        "course_id": normalized_course,
        "imported_at": datetime.now().isoformat(),
        "bm25_snapshot_path": bm25_snapshot_path,
    }
    _save(settings)


def list_course_index_info(settings: Settings | None = None) -> dict[str, dict]:
    if settings is None:
        settings = load_settings()
    grouped: dict[str, dict] = {}
    for doc_id, info in list_documents(settings).items():
        course_id = info.get("course_id", "默认课程")
        bucket = grouped.setdefault(course_id, {
            "chunk_count": 0,
            "doc_ids": [],
            "bm25_snapshot_path": info.get("bm25_snapshot_path", ""),
        })
        bucket["chunk_count"] += int(info.get("chunk_count", 0))
        bucket["doc_ids"].append(doc_id)
        if not bucket["bm25_snapshot_path"]:
            bucket["bm25_snapshot_path"] = info.get("bm25_snapshot_path", "")
    for course_id in grouped:
        grouped[course_id]["doc_ids"].sort()
    return grouped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_metadata.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/knowledge/test_metadata.py src/final_agent/knowledge/metadata.py
git commit -m "feat: record course-scoped knowledge metadata"
```

## Task 2: Split BM25 snapshots by course and support lazy scoped loading

**Files:**
- Create: `tests/knowledge/test_bm25_index.py`
- Modify: `src/final_agent/knowledge/bm25_index.py`
- Modify: `src/final_agent/knowledge/__init__.py`

- [ ] **Step 1: Write the failing BM25 partition tests**

```python
from __future__ import annotations


def test_build_index_for_course_writes_course_snapshot(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, course_index_path
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    chunks = [
        Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation testing"),
        Chunk(chunk_id="a2", doc_id="doc-a", course_id="course-a", text="branching strategy"),
    ]

    count = build_index_for_course("course-a", chunks, settings=settings)

    assert count == 2
    assert course_index_path("course-a", settings).exists()


def test_ensure_course_loaded_switches_sparse_cache(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, ensure_course_loaded, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    build_index_for_course("course-a", [Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation testing")], settings=settings)
    build_index_for_course("course-b", [Chunk(chunk_id="b1", doc_id="doc-b", course_id="course-b", text="database indexing")], settings=settings)

    ensure_course_loaded("course-b", settings=settings)
    results = search("database", top_k=5, course_ids=["course-b"])

    assert [chunk.chunk_id for chunk, _ in results] == ["b1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_bm25_index.py -v`

Expected: FAIL because `build_index_for_course()`, `course_index_path()`, and `ensure_course_loaded()` do not exist.

- [ ] **Step 3: Write the minimal partitioned BM25 implementation**

```python
_ACTIVE_COURSE_ID: Optional[str] = None


def course_index_path(course_id: str, settings: Settings) -> Path:
    normalized = course_id or "default"
    return Path(settings.vector_store.persist_dir) / f"bm25_{normalized}.json"


def build_index_for_course(course_id: str, chunks: list[Chunk], settings: Settings | None = None) -> int:
    global _INDEX_CACHE, _CHUNK_MAP_CACHE, _ACTIVE_COURSE_ID
    if settings is None:
        settings = load_settings()
    path = course_index_path(course_id, settings)
    scoped = [chunk for chunk in chunks if (chunk.course_id or "默认课程") == (course_id or "默认课程")]
    if not scoped:
        if path.exists():
            path.unlink()
        if _ACTIVE_COURSE_ID == course_id:
            _INDEX_CACHE = None
            _CHUNK_MAP_CACHE = None
            _ACTIVE_COURSE_ID = None
        return 0
    tokenized = [_tokenize(chunk.text) for chunk in scoped]
    bm25 = BM25Okapi(tokenized)
    data = {"chunk_ids": [chunk.chunk_id for chunk in scoped]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _INDEX_CACHE = bm25
    _CHUNK_MAP_CACHE = scoped
    _ACTIVE_COURSE_ID = course_id
    return len(scoped)


def ensure_course_loaded(course_id: str, *, settings: Settings | None = None, chunks: list[Chunk] | None = None) -> int:
    global _ACTIVE_COURSE_ID
    if settings is None:
        settings = load_settings()
    if _ACTIVE_COURSE_ID == course_id and _INDEX_CACHE is not None and _CHUNK_MAP_CACHE is not None:
        return len(_CHUNK_MAP_CACHE)
    scoped_chunks = list(chunks or [])
    path = course_index_path(course_id, settings)
    if not path.exists():
        return build_index_for_course(course_id, scoped_chunks, settings=settings)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    allowed_ids = set(persisted.get("chunk_ids", []))
    resolved = [chunk for chunk in scoped_chunks if chunk.chunk_id in allowed_ids]
    if not resolved:
        return build_index_for_course(course_id, scoped_chunks, settings=settings)
    tokenized = [_tokenize(chunk.text) for chunk in resolved]
    _INDEX_CACHE = BM25Okapi(tokenized)
    _CHUNK_MAP_CACHE = resolved
    _ACTIVE_COURSE_ID = course_id
    return len(resolved)
```

- [ ] **Step 4: Re-export the new helpers**

```python
from final_agent.knowledge.bm25_index import (
    build_index as build_index,
    build_index_for_course,
    course_index_path,
    ensure_course_loaded,
    search as bm25_search,
    load_index as bm25_load,
    delete_by_doc_id as bm25_delete_doc,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_bm25_index.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/knowledge/test_bm25_index.py src/final_agent/knowledge/bm25_index.py src/final_agent/knowledge/__init__.py
git commit -m "feat: add course-scoped bm25 snapshots"
```

## Task 3: Rebuild only the affected course during ingestion and deletion

**Files:**
- Modify: `src/final_agent/knowledge/builder.py`
- Modify: `src/final_agent/knowledge/metadata.py`
- Modify: `src/final_agent/knowledge/bm25_index.py`
- Test: `tests/knowledge/test_bm25_index.py`

- [ ] **Step 1: Extend the failing test for doc deletion**

```python
def test_delete_by_doc_id_rebuilds_only_affected_course(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, delete_by_doc_id, ensure_course_loaded, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    course_a = [
        Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation testing"),
        Chunk(chunk_id="a2", doc_id="doc-a", course_id="course-a", text="ci pipelines"),
    ]
    course_b = [Chunk(chunk_id="b1", doc_id="doc-b", course_id="course-b", text="database indexing")]

    build_index_for_course("course-a", course_a, settings=settings)
    build_index_for_course("course-b", course_b, settings=settings)

    removed = delete_by_doc_id("doc-a", settings=settings, course_id="course-a")
    ensure_course_loaded("course-b", settings=settings, chunks=course_b)

    assert removed == 2
    assert [chunk.chunk_id for chunk, _ in search("database", top_k=5, course_ids=["course-b"])] == ["b1"]
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_bm25_index.py::test_delete_by_doc_id_rebuilds_only_affected_course -v`

Expected: FAIL because `delete_by_doc_id()` does not accept `course_id`.

- [ ] **Step 3: Write the minimal incremental builder implementation**

```python
def build(
    chunks: list[Chunk],
    *,
    source_path: str = "",
    settings: Settings | None = None,
) -> dict:
    if settings is None:
        settings = load_settings()
    if not chunks:
        return {"chunks": 0, "doc_id": "", "bm25_docs": 0}

    doc_id = chunks[0].doc_id or "unknown"
    course_id = chunks[0].course_id or "默认课程"
    pairs = embed_chunks(chunks, settings=settings)
    add_chunks(pairs, settings=settings)

    from final_agent.knowledge.vector_store import get_chunks_by_doc, get_all_chunks

    all_chunks = get_all_chunks(settings=settings)
    scoped = [chunk for chunk in all_chunks if (chunk.course_id or "默认课程") == course_id]
    build_index_for_course(course_id, scoped, settings=settings)

    snapshot_path = str(course_index_path(course_id, settings))
    register_document(doc_id, source_path or doc_id, len(chunks), settings=settings, course_id=course_id, bm25_snapshot_path=snapshot_path)
    return {"chunks": len(chunks), "doc_id": doc_id, "course_id": course_id, "bm25_scope_chunks": len(scoped)}
```

```python
def delete_by_doc_id(
    doc_id: str,
    settings: Settings | None = None,
    *,
    course_id: str,
) -> int:
    if settings is None:
        settings = load_settings()
    remaining = [chunk for chunk in get_cached_chunks() if chunk.doc_id != doc_id]
    removed = len(get_cached_chunks()) - len(remaining)
    build_index_for_course(course_id, remaining, settings=settings)
    return removed
```

- [ ] **Step 4: Run the knowledge tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_metadata.py tests/knowledge/test_bm25_index.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/knowledge/builder.py src/final_agent/knowledge/metadata.py src/final_agent/knowledge/bm25_index.py tests/knowledge/test_metadata.py tests/knowledge/test_bm25_index.py
git commit -m "refactor: rebuild sparse index by course scope"
```

## Task 4: Make retrieval lazily load the scoped sparse partition

**Files:**
- Modify: `src/final_agent/retrieval/hybrid_searcher.py`
- Modify: `tests/retrieval/test_hybrid_searcher.py`

- [ ] **Step 1: Write the failing retrieval test**

```python
from __future__ import annotations


def test_hybrid_search_loads_sparse_scope_before_search(monkeypatch):
    from final_agent.retrieval import hybrid_searcher
    from final_agent.schemas import Chunk

    calls: dict[str, object] = {}
    shared = Chunk(chunk_id="shared", doc_id="doc-a", course_id="course-a", text="shared")

    monkeypatch.setattr(hybrid_searcher, "_dense_retrieve", lambda *args, **kwargs: [(shared, 0.8)])
    monkeypatch.setattr(hybrid_searcher, "ensure_course_loaded", lambda course_id, **kwargs: calls.setdefault("course_id", course_id) or 1)
    monkeypatch.setattr(hybrid_searcher, "bm25_search", lambda *args, **kwargs: [(shared, 2.0)])

    hybrid_searcher.hybrid_search("query", top_k=3, course_ids=["course-a"])

    assert calls["course_id"] == "course-a"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/retrieval/test_hybrid_searcher.py::test_hybrid_search_loads_sparse_scope_before_search -v`

Expected: FAIL because `hybrid_searcher` does not import or call `ensure_course_loaded()`.

- [ ] **Step 3: Write the minimal retrieval implementation**

```python
from final_agent.knowledge.bm25_index import ensure_course_loaded, search as bm25_search
from final_agent.knowledge.metadata import list_documents
from final_agent.knowledge.vector_store import query as chroma_query, get_all_chunks


def _sparse_retrieve(
    query: str, top_k: int, settings: Settings | None = None, course_ids: list[str] | None = None
) -> list[tuple[Chunk, float]]:
    if settings is None:
        settings = load_settings()
    course_id = course_ids[0] if course_ids and course_ids[0] else "默认课程"
    chunks = [chunk for chunk in get_all_chunks(settings=settings) if (chunk.course_id or "默认课程") == course_id]
    ensure_course_loaded(course_id, settings=settings, chunks=chunks)
    return bm25_search(query, top_k=top_k, course_ids=course_ids)
```

- [ ] **Step 4: Run retrieval tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/retrieval/test_hybrid_searcher.py tests/retrieval/test_pipeline.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/retrieval/hybrid_searcher.py tests/retrieval/test_hybrid_searcher.py
git commit -m "feat: lazy load sparse partitions during retrieval"
```

## Task 5: Remove blocking UI/API warmup and surface readiness

**Files:**
- Modify: `src/final_agent/ui/app.py`
- Modify: `src/final_agent/api/app.py`
- Test: `tests/retrieval/test_pipeline.py`

- [ ] **Step 1: Write the failing readiness test**

```python
from __future__ import annotations


def test_search_runs_without_global_bm25_warmup(monkeypatch):
    from final_agent.retrieval import pipeline
    from final_agent.schemas import Chunk, ScoredChunk
    from final_agent.settings import Settings

    settings = Settings()
    chunk = Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation")

    monkeypatch.setattr(pipeline, "expand_query", lambda q: [q])
    monkeypatch.setattr(pipeline, "hybrid_search", lambda *args, **kwargs: [ScoredChunk(chunk=chunk, score=0.8, source="rrf")])
    monkeypatch.setattr(pipeline, "rerank", lambda q, candidates, **kwargs: candidates)
    monkeypatch.setattr(pipeline, "filter_results", lambda candidates, **kwargs: candidates)

    results = pipeline.search("automation", settings=settings, course_ids=["course-a"])

    assert [sc.chunk.chunk_id for sc in results] == ["a1"]
```

- [ ] **Step 2: Run the targeted tests**

Run: `conda run -n final-agent python -m pytest tests/retrieval/test_pipeline.py -v`

Expected: PASS before UI/API edits; use this as the regression guard while removing startup warmup.

- [ ] **Step 3: Remove blocking warmup from FastAPI**

```python
def create_app(repository: MemoryRepository | None = None, quiz_generator=None, grader=None) -> FastAPI:
    app = FastAPI(title="final-agent Study Coach API")
    repo = MemoryRepository() if repository is None else repository
    service = AgentService(repo, quiz_generator=quiz_generator, grader=grader)
```

Delete the eager call:

```python
    _warm_knowledge_cache()
```

- [ ] **Step 4: Remove blocking warmup from Streamlit and add readiness text**

```python
def knowledge_status_text() -> str:
    from final_agent.knowledge.metadata import list_course_index_info

    info = list_course_index_info(st.session_state.settings)
    if not info:
        return "知识库状态：空"
    if app_state.course_id and app_state.course_id in info:
        return f"知识库状态：按课程惰性加载（{app_state.course_id}，{info[app_state.course_id]['chunk_count']} chunks）"
    return f"知识库状态：按课程惰性加载（{len(info)} 门课程）"
```

Replace the startup spinner block:

```python
with st.spinner("加载知识库..."):
    ensure_knowledge_loaded(str(app_state.build_counter))
st.empty()
```

with a lightweight status line:

```python
st.caption(knowledge_status_text())
```

- [ ] **Step 5: Run focused regressions**

Run: `conda run -n final-agent python -m pytest tests/knowledge/test_metadata.py tests/knowledge/test_bm25_index.py tests/retrieval/test_hybrid_searcher.py tests/retrieval/test_pipeline.py tests/api/test_sessions.py -v`

Expected: PASS

- [ ] **Step 6: Run lint and full regression**

Run: `conda run -n final-agent python -m ruff check src tests`
Expected: PASS

Run: `conda run -n final-agent python -m pytest --cov=final_agent --cov-report=term-missing`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/final_agent/ui/app.py src/final_agent/api/app.py tests/retrieval/test_pipeline.py
git commit -m "perf: remove blocking knowledge warmup"
```

## Self-Review

- Spec coverage: covers the previously identified P0/P1 work only: startup warmup removal, course-scoped BM25 partitions, lazy retrieval loading, and metadata needed to route them.
- Placeholder scan: no `TBD`, `TODO`, or implicit “write tests later” steps remain.
- Type consistency: all later tasks use the same names introduced earlier: `bm25_snapshot_path`, `list_course_index_info`, `build_index_for_course`, `course_index_path`, and `ensure_course_loaded`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-knowledgebase-scaling.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
