"""Embedding service — wraps sentence-transformers for chunk vectorisation."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_EMBEDDER_CACHE: Optional[SentenceTransformer] = None
_EMBEDDER_MODEL_NAME: Optional[str] = None


def _get_model(settings: Settings) -> SentenceTransformer:
    """Load (or reuse) the embedding model."""
    global _EMBEDDER_CACHE, _EMBEDDER_MODEL_NAME
    model_name = settings.models_embedding.model_name
    device = settings.models_embedding.device
    if _EMBEDDER_CACHE is not None and _EMBEDDER_MODEL_NAME == model_name:
        return _EMBEDDER_CACHE
    logger.info("Loading embedding model: %s (device=%s)", model_name, device)
    _EMBEDDER_CACHE = SentenceTransformer(model_name, device=device)
    _EMBEDDER_MODEL_NAME = model_name
    return _EMBEDDER_CACHE


def embed_texts(
    texts: list[str],
    settings: Settings | None = None,
    *,
    batch_size: int = 32,
    show_progress: bool = False,
) -> np.ndarray:
    """Convert a list of texts to dense vectors.

    Args:
        texts: Plain-text strings to embed.
        settings: Application settings (auto-loaded if omitted).
        batch_size: Encoding batch size.
        show_progress: Whether to display a progress bar.

    Returns:
        ``(n, d)`` float32 array where *n* = len(texts).
    """
    if settings is None:
        settings = load_settings()
    model = _get_model(settings)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings  # type: ignore[return-value]


def embed_chunks(
    chunks: list[Chunk],
    settings: Settings | None = None,
) -> list[tuple[Chunk, np.ndarray]]:
    """Embed a batch of chunks, returning (chunk, vector) pairs.

    Args:
        chunks: List of ``Chunk`` objects.
        settings: Application settings.

    Returns:
        List of (chunk, 1-d float32 vector) pairs in the same order.
    """
    if not chunks:
        return []
    texts = [c.text for c in chunks]
    vectors = embed_texts(texts, settings=settings)
    return list(zip(chunks, vectors))
