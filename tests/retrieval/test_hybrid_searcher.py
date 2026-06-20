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
