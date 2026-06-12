"""Threshold filter — discard low-quality retrieval results."""

from __future__ import annotations

from final_agent.schemas import ScoredChunk
from final_agent.settings import Settings, load_settings


def filter_results(
    candidates: list[ScoredChunk],
    settings: Settings | None = None,
    *,
    similarity_threshold: float | None = None,
    min_matches: int | None = None,
) -> list[ScoredChunk]:
    """Remove results below similarity threshold; ensure min_matches.

    If fewer than *min_matches* survive, return the best *min_matches* anyway.
    """
    if settings is None:
        settings = load_settings()
    if similarity_threshold is None:
        similarity_threshold = settings.retrieval.similarity_threshold
    if min_matches is None:
        min_matches = settings.retrieval.min_matches

    above = [c for c in candidates if c.score >= similarity_threshold]
    if len(above) < min_matches:
        return candidates[:min_matches]
    return above
