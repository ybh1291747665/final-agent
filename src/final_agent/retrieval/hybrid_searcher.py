"""Hybrid searcher — parallel dense+sparse retrieval with RRF fusion."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from final_agent.knowledge.bm25_index import search as bm25_search
from final_agent.knowledge.embedder import embed_texts
from final_agent.knowledge.vector_store import query as chroma_query
from final_agent.schemas import Chunk, ScoredChunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

# RRF constant — controls rank decay
RRF_K = 60


def hybrid_search(
    query: str,
    settings: Settings | None = None,
    *,
    top_k: int = 10,
    dense_weight: float | None = None,
    sparse_weight: float | None = None,
    course_ids: list[str] | None = None,
) -> list[ScoredChunk]:
    """Run dense (Chroma) and sparse (BM25) retrieval in parallel, fuse with RRF.

    Args:
        query: User query string.
        settings: Application settings.
        top_k: Final result count.
        dense_weight: RRF weight for dense path (default from config).
        sparse_weight: RRF weight for sparse path (default from config).

    Returns:
        RRF-fused ``ScoredChunk`` list, best first, limited to *top_k*.
    """
    if settings is None:
        settings = load_settings()

    if dense_weight is None:
        dense_weight = settings.retrieval.dense_weight
    if sparse_weight is None:
        sparse_weight = settings.retrieval.bm25_weight

    # Fetch more candidates per path to give RRF enough to work with
    fetch_k = max(top_k * 3, 30)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_dense = executor.submit(_dense_retrieve, query, fetch_k, settings, course_ids)
        future_sparse = executor.submit(_sparse_retrieve, query, fetch_k, settings, course_ids)

        dense_results = future_dense.result()
        sparse_results = future_sparse.result()

    # RRF fusion
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    for rank, (chunk, _) in enumerate(dense_results):
        rrf_scores[chunk.chunk_id] = dense_weight / (RRF_K + rank + 1)
        chunk_map[chunk.chunk_id] = chunk

    for rank, (chunk, _) in enumerate(sparse_results):
        rid = chunk.chunk_id
        rrf_scores[rid] = rrf_scores.get(rid, 0.0) + sparse_weight / (RRF_K + rank + 1)
        if rid not in chunk_map:
            chunk_map[rid] = chunk

    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]  # type: ignore[arg-type]

    return [
        ScoredChunk(chunk=chunk_map[cid], score=rrf_scores[cid], source="rrf")
        for cid in sorted_ids
    ]


def _dense_retrieve(
    query: str, top_k: int, settings: Settings, course_ids: list[str] | None = None
) -> list[tuple[Chunk, float]]:
    qv = embed_texts([query], settings=settings)
    return chroma_query(qv[0], top_k=top_k, settings=settings, course_ids=course_ids)


def _sparse_retrieve(
    query: str, top_k: int, settings: Settings | None = None, course_ids: list[str] | None = None
) -> list[tuple[Chunk, float]]:
    return bm25_search(query, top_k=top_k, course_ids=course_ids)
