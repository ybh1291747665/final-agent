"""Retrieval pipeline — query expansion → hybrid search → rerank → filter."""

from __future__ import annotations

from final_agent.retrieval.filter import filter_results
from final_agent.retrieval.hybrid_searcher import hybrid_search
from final_agent.retrieval.query_expander import expand_query
from final_agent.retrieval.reranker import rerank
from final_agent.schemas import ScoredChunk
from final_agent.settings import Settings, load_settings


def search(
    query: str,
    settings: Settings | None = None,
    *,
    top_k: int | None = None,
    expand: bool = True,
    course_ids: list[str] | None = None,
) -> list[ScoredChunk]:
    """End-to-end retrieval: expand → hybrid → rerank → filter.

    Args:
        query: Natural-language query.
        settings: Application settings.
        top_k: Final result count (default from config).
        expand: Whether to use query expansion.
        course_ids: Optional course filter.

    Returns:
        Filtered and reranked ``ScoredChunk`` list.
    """
    if settings is None:
        settings = load_settings()
    if top_k is None:
        top_k = settings.retrieval.top_k

    query = query.strip()

    if expand:
        variants = expand_query(query)
        all_candidates: dict[str, ScoredChunk] = {}
        for v in variants:
            for sc in hybrid_search(v, settings=settings, top_k=top_k * 2, course_ids=course_ids):
                if sc.chunk.chunk_id not in all_candidates:
                    all_candidates[sc.chunk.chunk_id] = sc
        candidates = list(all_candidates.values())
    else:
        candidates = hybrid_search(query, settings=settings, top_k=top_k * 2, course_ids=course_ids)

    reranked = rerank(query, candidates, settings=settings, top_k=top_k * 2)
    filtered = filter_results(reranked, settings=settings)
    return filtered[:top_k]


def deep_search(
    query: str,
    settings: Settings | None = None,
    *,
    course_ids: list[str] | None = None,
) -> list[ScoredChunk]:
    """High-recall retrieval for review mode: more candidates, lower threshold, neighbor expansion.

    Differs from ``search()`` by:
    - Fetching ``review_top_k`` candidates instead of ``top_k``
    - Lower ``review_similarity_threshold`` to keep more matches
    - Expanding each hit with ``neighbor_expand`` adjacent chunks (same doc, nearby char_start)
    - Deduplicating: at most 2 chunks per heading_path
    """
    if settings is None:
        settings = load_settings()

    r = settings.retrieval
    query = query.strip()

    # 1. High-recall hybrid search
    fetch_k = max(r.review_top_k * 3, 60)
    variants = expand_query(query)
    all_candidates: dict[str, ScoredChunk] = {}
    for v in variants:
        for sc in hybrid_search(v, settings=settings, top_k=fetch_k, course_ids=course_ids):
            if sc.chunk.chunk_id not in all_candidates:
                all_candidates[sc.chunk.chunk_id] = sc
    candidates = list(all_candidates.values())

    # 2. Rerank with more candidates
    reranked = rerank(query, candidates, settings=settings, top_k=r.review_top_k * 2)

    # 3. Low-threshold filter
    filtered = filter_results(
        reranked, settings=settings,
        similarity_threshold=r.review_similarity_threshold,
        min_matches=max(r.review_top_k // 2, 5),
    )

    # 4. Neighbor expansion: for each hit, pull adjacent chunks from same doc
    from final_agent.knowledge.vector_store import get_chunks_by_doc as _chroma_doc
    seen_ids: set[str] = {sc.chunk.chunk_id for sc in filtered}
    expanded: dict[str, ScoredChunk] = {sc.chunk.chunk_id: sc for sc in filtered}

    if r.neighbor_expand > 0:
        for sc in list(filtered):
            doc_chunks = _chroma_doc(sc.chunk.doc_id, settings=settings)
            # Find neighbors by char_start proximity
            doc_chunks.sort(key=lambda c: c.char_start)
            try:
                idx = next(i for i, c in enumerate(doc_chunks) if c.chunk_id == sc.chunk.chunk_id)
            except StopIteration:
                continue
            # Pull neighbors before and after
            for offset in range(1, r.neighbor_expand + 1):
                for nb_idx in (idx - offset, idx + offset):
                    if 0 <= nb_idx < len(doc_chunks):
                        nb = doc_chunks[nb_idx]
                        if nb.chunk_id not in seen_ids:
                            seen_ids.add(nb.chunk_id)
                            expanded[nb.chunk_id] = ScoredChunk(
                                chunk=nb, score=sc.score * 0.8, source="neighbor"
                            )

    # 5. Deduplicate: max 2 per heading_path
    heading_counts: dict[str, int] = {}
    final: list[ScoredChunk] = []
    all_scored = sorted(expanded.values(), key=lambda x: x.score, reverse=True)
    for sc in all_scored:
        hp = "/".join(sc.chunk.heading_path) if sc.chunk.heading_path else "(top)"
        if heading_counts.get(hp, 0) < 2:
            heading_counts[hp] = heading_counts.get(hp, 0) + 1
            final.append(sc)

    return final[:r.review_top_k]
