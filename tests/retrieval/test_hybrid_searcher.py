from __future__ import annotations


def test_hybrid_search_rrf_boosts_chunks_found_by_both_paths(monkeypatch):
    from final_agent.retrieval import hybrid_searcher
    from final_agent.schemas import Chunk

    shared = Chunk(chunk_id="shared", text="shared")
    dense_only = Chunk(chunk_id="dense", text="dense")
    sparse_only = Chunk(chunk_id="sparse", text="sparse")

    monkeypatch.setattr(hybrid_searcher, "_dense_retrieve", lambda *args, **kwargs: [(dense_only, 0.9), (shared, 0.8)])
    monkeypatch.setattr(hybrid_searcher, "_sparse_retrieve", lambda *args, **kwargs: [(shared, 3.0), (sparse_only, 2.0)])

    results = hybrid_searcher.hybrid_search("query", top_k=3, dense_weight=1.0, sparse_weight=1.0)

    assert [r.chunk.chunk_id for r in results][0] == "shared"
    assert {r.source for r in results} == {"rrf"}


def test_hybrid_search_loads_sparse_scope_before_search(monkeypatch):
    from final_agent.retrieval import hybrid_searcher
    from final_agent.schemas import Chunk

    calls: dict[str, object] = {}
    shared = Chunk(chunk_id="shared", doc_id="doc-a", course_id="course-a", text="shared")

    monkeypatch.setattr(hybrid_searcher, "_dense_retrieve", lambda *args, **kwargs: [(shared, 0.8)])
    monkeypatch.setattr(
        hybrid_searcher,
        "ensure_course_loaded",
        lambda course_id, **kwargs: calls.setdefault("course_id", course_id) or 1,
    )
    monkeypatch.setattr(hybrid_searcher, "bm25_search", lambda *args, **kwargs: [(shared, 2.0)])

    hybrid_searcher.hybrid_search("query", top_k=3, course_ids=["course-a"])

    assert calls["course_id"] == "course-a"


def test_sparse_retrieve_loads_each_requested_course_without_global_chunk_scan(monkeypatch):
    from final_agent.retrieval import hybrid_searcher
    from final_agent.schemas import Chunk

    calls: list[str] = []

    monkeypatch.setattr(
        hybrid_searcher,
        "get_all_chunks",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("global chunk scan should not run")),
        raising=False,
    )
    monkeypatch.setattr(hybrid_searcher, "ensure_course_loaded", lambda course_id, **kwargs: calls.append(course_id) or 1)
    monkeypatch.setattr(
        hybrid_searcher,
        "bm25_search",
        lambda *args, **kwargs: [
            (
                Chunk(
                    chunk_id=f"{kwargs['course_ids'][0]}-chunk",
                    doc_id=f"{kwargs['course_ids'][0]}-doc",
                    course_id=kwargs["course_ids"][0],
                    text=kwargs["course_ids"][0],
                ),
                2.0 if kwargs["course_ids"][0] == "course-a" else 1.0,
            )
        ],
    )

    results = hybrid_searcher._sparse_retrieve("query", top_k=5, course_ids=["course-a", "course-b"])

    assert calls == ["course-a", "course-b"]
    assert [chunk.chunk_id for chunk, _ in results] == ["course-a-chunk", "course-b-chunk"]


def test_sparse_retrieve_uses_all_registered_courses_when_scope_missing(monkeypatch):
    from final_agent.retrieval import hybrid_searcher
    from final_agent.schemas import Chunk

    calls: list[str] = []

    monkeypatch.setattr(
        hybrid_searcher,
        "list_course_index_info",
        lambda settings=None: {
            "course-a": {"chunk_count": 2, "doc_ids": ["doc-a"], "bm25_snapshot_path": "a.json"},
            "course-b": {"chunk_count": 1, "doc_ids": ["doc-b"], "bm25_snapshot_path": "b.json"},
        },
    )
    monkeypatch.setattr(hybrid_searcher, "ensure_course_loaded", lambda course_id, **kwargs: calls.append(course_id) or 1)
    monkeypatch.setattr(
        hybrid_searcher,
        "bm25_search",
        lambda *args, **kwargs: [
            (
                Chunk(
                    chunk_id=f"{kwargs['course_ids'][0]}-chunk",
                    doc_id=f"{kwargs['course_ids'][0]}-doc",
                    course_id=kwargs["course_ids"][0],
                    text=kwargs["course_ids"][0],
                ),
                2.0 if kwargs["course_ids"][0] == "course-a" else 1.0,
            )
        ],
    )

    results = hybrid_searcher._sparse_retrieve("query", top_k=5, course_ids=None)

    assert calls == ["course-a", "course-b"]
    assert [chunk.chunk_id for chunk, _ in results] == ["course-a-chunk", "course-b-chunk"]
