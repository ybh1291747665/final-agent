"""Hallucination guard — L2 semantic consistency check via cross-encoder."""

from __future__ import annotations

import re
import logging
from typing import Optional

from sentence_transformers import CrossEncoder

from final_agent.schemas import Chunk, GeneratedAnswer, HallucinationFlag, VerifiedAnswer
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_RERANKER_CACHE: Optional[CrossEncoder] = None
_RERANKER_MODEL_NAME: Optional[str] = None

_CITATION_LINE_RE = re.compile(r"([^.!?\n]*\[([a-f0-9]{8,16})\][^.!?\n]*[.!?\n]?)")


def _get_reranker(settings: Settings) -> CrossEncoder:
    global _RERANKER_CACHE, _RERANKER_MODEL_NAME
    model_name = settings.models_reranker.model_name
    device = settings.models_reranker.device
    if _RERANKER_CACHE is not None and _RERANKER_MODEL_NAME == model_name:
        return _RERANKER_CACHE
    logger.info("Loading reranker for hallucination guard: %s", model_name)
    _RERANKER_CACHE = CrossEncoder(model_name, device=device)
    _RERANKER_MODEL_NAME = model_name
    return _RERANKER_CACHE


def verify_answer(
    generated: GeneratedAnswer,
    chunk_map: dict[str, Chunk],
    settings: Settings | None = None,
    *,
    threshold: float = 0.3,
) -> VerifiedAnswer:
    """Check a generated answer for potential hallucinations (L2).

    For each sentence containing a [chunk_id] citation, compute the
    cross-encoder similarity between the sentence and the cited chunk.
    Sentences below *threshold* are flagged.

    Args:
        generated: The GeneratedAnswer to verify.
        chunk_map: {chunk_id: Chunk} lookup of all retrieved chunks.
        settings: Application settings.
        threshold: Minimum cross-encoder score to pass.

    Returns:
        VerifiedAnswer with hallucination flags.
    """
    if settings is None:
        settings = load_settings()

    model = _get_reranker(settings)
    flags: list[HallucinationFlag] = []
    sentences = _extract_cited_sentences(generated.answer)

    if not sentences:
        return VerifiedAnswer(raw_answer=generated.answer, is_clean=True)

    pairs: list[tuple[str, str]] = []
    sent_info: list[tuple[str, str]] = []  # (sentence, chunk_id)

    for sentence, chunk_id in sentences:
        chunk = chunk_map.get(chunk_id)
        if chunk:
            pairs.append((sentence, chunk.text))
            sent_info.append((sentence, chunk_id))

    if not pairs:
        return VerifiedAnswer(raw_answer=generated.answer, is_clean=True)

    scores = model.predict(pairs, show_progress_bar=False)

    for i, (sentence, chunk_id) in enumerate(sent_info):
        sim = float(scores[i])
        flagged = sim < threshold
        flags.append(HallucinationFlag(
            sentence=sentence.strip(),
            cited_chunk_id=chunk_id,
            similarity_score=sim,
            flagged=flagged,
        ))

    return VerifiedAnswer(
        raw_answer=generated.answer,
        flags=flags,
        is_clean=all(not f.flagged for f in flags),
    )


def _extract_cited_sentences(text: str) -> list[tuple[str, str]]:
    """Return list of (sentence, chunk_id) for every sentence with a citation."""
    results: list[tuple[str, str]] = []
    for m in _CITATION_LINE_RE.finditer(text):
        sentence = m.group(1)
        chunk_id = m.group(2)
        if sentence.strip():
            results.append((sentence, chunk_id))
    return results
