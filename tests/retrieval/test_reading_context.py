from __future__ import annotations


def test_chunk_index_text_includes_heading_page_and_body():
    from final_agent.retrieval_context import chunk_index_text
    from final_agent.schemas import Chunk

    chunk = Chunk(
        text="Automated tests run on every commit.",
        heading_path=["DevOps", "Continuous Integration"],
        page_num=12,
    )

    assert chunk_index_text(chunk) == (
        "DevOps > Continuous Integration\nPage 12\n"
        "Automated tests run on every commit."
    )


def test_reading_context_promotes_only_close_relevant_candidates():
    from final_agent.retrieval_context import apply_reading_context
    from final_agent.schemas import Chunk, ReadingContext, ScoredChunk

    results = [
        ScoredChunk(
            chunk=Chunk(chunk_id="best", doc_id="other", page_num=2, text="best"),
            score=0.95,
            source="rerank",
        ),
        ScoredChunk(
            chunk=Chunk(chunk_id="near", doc_id="doc-a", page_num=12, text="near"),
            score=0.92,
            source="rerank",
        ),
        ScoredChunk(
            chunk=Chunk(chunk_id="weak", doc_id="doc-a", page_num=12, text="weak"),
            score=0.10,
            source="rerank",
        ),
    ]

    ranked = apply_reading_context(
        results,
        ReadingContext(doc_id="doc-a", page_num=12),
    )

    assert [result.chunk.chunk_id for result in ranked] == ["near", "best", "weak"]
    assert {result.chunk.chunk_id for result in ranked} == {"best", "near", "weak"}


def test_disabled_reading_context_preserves_order():
    from final_agent.retrieval_context import apply_reading_context
    from final_agent.schemas import Chunk, ReadingContext, ScoredChunk

    results = [
        ScoredChunk(chunk=Chunk(chunk_id="a", doc_id="other", page_num=1), score=0.8),
        ScoredChunk(chunk=Chunk(chunk_id="b", doc_id="doc-a", page_num=2), score=0.7),
    ]

    ranked = apply_reading_context(
        results,
        ReadingContext(doc_id="doc-a", page_num=2, page_boost_enabled=False),
    )

    assert [result.chunk.chunk_id for result in ranked] == ["a", "b"]


def test_embed_chunks_uses_contextual_index_text(monkeypatch):
    from final_agent.knowledge import embedder
    from final_agent.schemas import Chunk

    captured: list[str] = []

    def fake_embed_texts(texts, settings=None):
        import numpy as np

        captured.extend(texts)
        return np.array([[1.0, 0.0]])

    monkeypatch.setattr(embedder, "embed_texts", fake_embed_texts)

    embedder.embed_chunks(
        [Chunk(text="Body", heading_path=["Heading"], page_num=3)]
    )

    assert captured == ["Heading\nPage 3\nBody"]


def test_reranker_uses_contextual_index_text(monkeypatch):
    from final_agent.retrieval import reranker
    from final_agent.schemas import Chunk, ScoredChunk

    captured = []

    class FakeModel:
        def predict(self, pairs, show_progress_bar=False):
            captured.extend(pairs)
            return [0.9]

    monkeypatch.setattr(reranker, "_get_model", lambda settings: FakeModel())

    reranker.rerank(
        "question",
        [
            ScoredChunk(
                chunk=Chunk(text="Body", heading_path=["Heading"], page_num=3),
                score=0.2,
            )
        ],
    )

    assert captured == [("question", "Heading\nPage 3\nBody")]


def test_search_applies_reading_context_after_filtering(monkeypatch):
    from final_agent.retrieval import pipeline
    from final_agent.schemas import Chunk, ReadingContext, ScoredChunk

    candidates = [
        ScoredChunk(chunk=Chunk(chunk_id="a", doc_id="other", page_num=1), score=0.8),
        ScoredChunk(chunk=Chunk(chunk_id="b", doc_id="doc-a", page_num=12), score=0.79),
        ScoredChunk(chunk=Chunk(chunk_id="c", doc_id="other", page_num=4), score=0.1),
    ]
    monkeypatch.setattr(pipeline, "expand_query", lambda query: [query])
    monkeypatch.setattr(pipeline, "hybrid_search", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(pipeline, "rerank", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(pipeline, "filter_results", lambda results, settings=None: results)

    results = pipeline.search(
        "question",
        reading_context=ReadingContext(doc_id="doc-a", page_num=12),
    )

    assert [result.chunk.chunk_id for result in results] == ["b", "a", "c"]
