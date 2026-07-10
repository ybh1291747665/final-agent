"""Reranker — bge-reranker-v2-m3 cross-encoder for precision re-ranking."""

from __future__ import annotations

import logging
from typing import Optional

try:
    from sentence_transformers import CrossEncoder
except ModuleNotFoundError:
    CrossEncoder = None  # type: ignore[assignment]

from final_agent.schemas import ScoredChunk
from final_agent.retrieval_context import chunk_index_text
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_RERANKER_CACHE: Optional["CrossEncoder"] = None
_RERANKER_MODEL_NAME: Optional[str] = None


def _get_model(settings: Settings):
    global _RERANKER_CACHE, _RERANKER_MODEL_NAME
    if CrossEncoder is None:
        raise RuntimeError("sentence-transformers is not installed; install project dependencies to rerank.")
    model_name = settings.models_reranker.model_name
    device = settings.models_reranker.device
    if _RERANKER_CACHE is not None and _RERANKER_MODEL_NAME == model_name:
        return _RERANKER_CACHE
    logger.info("Loading reranker: %s (device=%s)", model_name, device)
    _RERANKER_CACHE = CrossEncoder(model_name, device=device)
    _RERANKER_MODEL_NAME = model_name
    return _RERANKER_CACHE


def rerank(
    query: str,
    candidates: list[ScoredChunk],
    settings: Settings | None = None,
    *,
    top_k: int = 10,
) -> list[ScoredChunk]:
    """Rerank RRF-fused candidates with the cross-encoder.

    Args:
        query: User query.
        candidates: RRF-fused ``ScoredChunk`` list.
        settings: Application settings.
        top_k: Limit after re-ranking.

    Returns:
        Reranked ``ScoredChunk`` list, best first.
    """
    if not candidates:
        return []
    if settings is None:
        settings = load_settings()
    model = _get_model(settings)

    pairs = [(query, chunk_index_text(c.chunk)) for c in candidates]
    scores = model.predict(pairs, show_progress_bar=False)

    scored = [
        ScoredChunk(chunk=candidates[i].chunk, score=float(scores[i]), source="rerank")
        for i in range(len(candidates))
    ]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]
