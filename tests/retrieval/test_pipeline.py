from __future__ import annotations


def test_deep_search_expands_neighbors_and_caps_heading_duplicates(monkeypatch):
    from final_agent.retrieval import pipeline
    from final_agent.schemas import Chunk, ScoredChunk
    from final_agent.settings import Settings

    base = Chunk(chunk_id="hit", doc_id="doc", course_id="course-a", text="hit", heading_path=["Same"], char_start=10)
    n1 = Chunk(chunk_id="n1", doc_id="doc", course_id="course-a", text="before", heading_path=["Same"], char_start=0)
    n2 = Chunk(chunk_id="n2", doc_id="doc", course_id="course-a", text="after", heading_path=["Same"], char_start=20)
    n3 = Chunk(chunk_id="n3", doc_id="doc", course_id="course-a", text="next", heading_path=["Same"], char_start=30)

    settings = Settings()
    settings.retrieval.review_top_k = 10
    settings.retrieval.neighbor_expand = 2

    monkeypatch.setattr(pipeline, "expand_query", lambda q: [q])
    monkeypatch.setattr(pipeline, "hybrid_search", lambda *args, **kwargs: [ScoredChunk(chunk=base, score=0.95, source="rrf")])
    monkeypatch.setattr(pipeline, "rerank", lambda q, candidates, **kwargs: candidates)
    monkeypatch.setattr(pipeline, "filter_results", lambda candidates, **kwargs: candidates)

    import final_agent.knowledge.vector_store as vector_store

    monkeypatch.setattr(vector_store, "get_chunks_by_doc", lambda *args, **kwargs: [n1, base, n2, n3])

    results = pipeline.deep_search("query", settings=settings, course_ids=["course-a"])

    assert len([r for r in results if r.chunk.heading_path == ["Same"]]) == 2
    assert "hit" in {r.chunk.chunk_id for r in results}
    assert any(r.source == "neighbor" for r in results)
