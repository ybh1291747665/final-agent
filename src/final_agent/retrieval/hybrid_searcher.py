"""Hybrid searcher - parallel dense+sparse retrieval with RRF fusion."""

from __future__ import annotations

import logging
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor

from final_agent.knowledge.bm25_index import ensure_course_loaded, search as bm25_search
from final_agent.knowledge.embedder import embed_texts
from final_agent.knowledge.metadata import list_course_index_info
from final_agent.knowledge.vector_store import query as chroma_query
from final_agent.runtime_monitoring import get_runtime_monitor
from final_agent.schemas import Chunk, ScoredChunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

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
    """Run dense and sparse retrieval in parallel, then fuse them with RRF."""
    started_at = perf_counter()
    if settings is None:
        settings = load_settings()

    if dense_weight is None:
        dense_weight = settings.retrieval.dense_weight
    if sparse_weight is None:
        sparse_weight = settings.retrieval.bm25_weight

    fetch_k = max(top_k * 3, 30)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_dense = executor.submit(_dense_retrieve, query, fetch_k, settings, course_ids)
        future_sparse = executor.submit(_sparse_retrieve, query, fetch_k, settings, course_ids)

        dense_results = future_dense.result()
        sparse_results = future_sparse.result()

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    for rank, (chunk, _) in enumerate(dense_results):
        rrf_scores[chunk.chunk_id] = dense_weight / (RRF_K + rank + 1)
        chunk_map[chunk.chunk_id] = chunk

    for rank, (chunk, _) in enumerate(sparse_results):
        chunk_id = chunk.chunk_id
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + sparse_weight / (RRF_K + rank + 1)
        if chunk_id not in chunk_map:
            chunk_map[chunk_id] = chunk

    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
    results = [
        ScoredChunk(chunk=chunk_map[chunk_id], score=rrf_scores[chunk_id], source="rrf")
        for chunk_id in sorted_ids
    ]
    latency_ms = (perf_counter() - started_at) * 1000
    get_runtime_monitor().record_retrieval(
        latency_ms=latency_ms,
        course_ids=course_ids,
        result_course_ids=[result.chunk.course_id for result in results],
    )
    return results


def _dense_retrieve(
    query: str, top_k: int, settings: Settings, course_ids: list[str] | None = None
) -> list[tuple[Chunk, float]]:
    query_vector = embed_texts([query], settings=settings)
    return chroma_query(query_vector[0], top_k=top_k, settings=settings, course_ids=course_ids)


def _sparse_retrieve(
    query: str, top_k: int, settings: Settings | None = None, course_ids: list[str] | None = None
) -> list[tuple[Chunk, float]]:
    if settings is None:
        settings = load_settings()

    scoped_course_ids = _resolve_sparse_course_ids(settings, course_ids)
    if not scoped_course_ids:
        return []

    merged: dict[str, tuple[Chunk, float]] = {}
    for course_id in scoped_course_ids:
        ensure_course_loaded(course_id, settings=settings)
        for chunk, score in bm25_search(query, top_k=top_k, course_ids=[course_id]):
            current = merged.get(chunk.chunk_id)
            if current is None or score > current[1]:
                merged[chunk.chunk_id] = (chunk, score)

    return sorted(merged.values(), key=lambda item: item[1], reverse=True)[:top_k]


def _resolve_sparse_course_ids(settings: Settings, course_ids: list[str] | None) -> list[str]:
    explicit_course_ids = [course_id for course_id in (course_ids or []) if course_id]
    if explicit_course_ids:
        return list(dict.fromkeys(explicit_course_ids))
    return list(list_course_index_info(settings).keys())
