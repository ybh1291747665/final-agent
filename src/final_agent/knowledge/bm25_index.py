"""BM25 sparse index — jieba tokenisation + JSON persistence."""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
try:
    from rank_bm25 import BM25Okapi
except ModuleNotFoundError:
    class BM25Okapi:  # type: ignore[no-redef]
        def __init__(self, tokenized: list[list[str]]):
            self.corpus = tokenized
            self.corpus_size = len(tokenized)
            self.doc_len = [len(doc) for doc in tokenized]
            self.doc_freqs = []
            self.idf = {}
            self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
            self.k1 = 1.5
            self.b = 0.75
            self.epsilon = 0.25

        def get_scores(self, tokens: list[str]) -> np.ndarray:
            token_set = set(tokens)
            return np.array([sum(1 for token in doc if token in token_set) for doc in self.corpus], dtype=float)

from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_INDEX_CACHE: Optional[BM25Okapi] = None
_CHUNK_MAP_CACHE: Optional[list[Chunk]] = None


def _bm25_index_path(settings: Settings) -> Path:
    return Path(settings.vector_store.persist_dir) / "bm25_index.json"


def _tokenize(text: str) -> list[str]:
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="pkg_resources is deprecated as an API.*",
                category=UserWarning,
            )
            import jieba

        return [t.strip() for t in jieba.cut(text) if t.strip()]
    except ModuleNotFoundError:
        import re

        return [t for t in re.split(r"\W+", text.lower()) if t]


def build_index(
    chunks: list[Chunk],
    settings: Settings | None = None,
) -> int:
    """Build (or rebuild) the BM25 index from *all* chunks and persist to JSON.

    This is a full rebuild — pass the complete chunk list (old + new).
    """
    global _INDEX_CACHE, _CHUNK_MAP_CACHE
    if settings is None:
        settings = load_settings()

    if not chunks:
        _INDEX_CACHE = None
        _CHUNK_MAP_CACHE = None
        path = _bm25_index_path(settings)
        if path.exists():
            path.unlink()
        return 0

    tokenized = [_tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    _INDEX_CACHE = bm25
    _CHUNK_MAP_CACHE = list(chunks)

    data = {
        "corpus_size": bm25.corpus_size,
        "doc_len": bm25.doc_len,
        "doc_freqs": bm25.doc_freqs,
        "idf": bm25.idf,
        "avgdl": bm25.avgdl,
        "k1": bm25.k1,
        "b": bm25.b,
        "epsilon": bm25.epsilon,
        "chunk_ids": [c.chunk_id for c in chunks],
    }
    path = _bm25_index_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("BM25 index built: %d chunks -> %s", len(chunks), path)
    return len(chunks)


def load_index(
    chunks: list[Chunk],
    settings: Settings | None = None,
) -> int:
    """Restore BM25 index from JSON. Falls back to build_index if missing."""
    global _INDEX_CACHE, _CHUNK_MAP_CACHE
    if settings is None:
        settings = load_settings()
    path = _bm25_index_path(settings)

    if not path.exists() or not chunks:
        return build_index(chunks, settings)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return build_index(chunks, settings)

    persisted_ids = set(data.get("chunk_ids", []))
    resolved = [c for c in chunks if c.chunk_id in persisted_ids]
    if not resolved:
        return build_index(chunks, settings)

    tokenized = [_tokenize(c.text) for c in resolved]
    bm25 = BM25Okapi(tokenized)
    _INDEX_CACHE = bm25
    _CHUNK_MAP_CACHE = resolved

    logger.info("BM25 index loaded: %d chunks from %s", len(resolved), path)
    return len(resolved)


def search(
    query: str,
    top_k: int = 10,
    *,
    course_ids: list[str] | None = None,
) -> list[tuple[Chunk, float]]:
    global _INDEX_CACHE, _CHUNK_MAP_CACHE
    if _INDEX_CACHE is None or _CHUNK_MAP_CACHE is None:
        raise RuntimeError("BM25 index not loaded. Call load_index() first.")
    tokens = _tokenize(query)
    scores = _INDEX_CACHE.get_scores(tokens)
    top_indices = np.argsort(scores)[::-1]
    results: list[tuple[Chunk, float]] = []
    for idx in top_indices:
        if idx >= len(_CHUNK_MAP_CACHE) or scores[idx] <= 0:
            continue
        chunk = _CHUNK_MAP_CACHE[idx]
        # Filter by course if requested
        if course_ids and course_ids[0] and chunk.course_id not in course_ids:
            continue
        results.append((chunk, float(scores[idx])))
        if len(results) >= top_k:
            break
    return results


def get_cached_chunks() -> list[Chunk]:
    """Return chunks currently in the in-memory BM25 cache."""
    return list(_CHUNK_MAP_CACHE) if _CHUNK_MAP_CACHE else []


def delete_by_doc_id(
    doc_id: str,
    settings: Settings | None = None,
) -> int:
    """Remove chunks with *doc_id* from BM25 index and rebuild."""
    global _INDEX_CACHE, _CHUNK_MAP_CACHE
    if settings is None:
        settings = load_settings()
    existing = get_cached_chunks()
    remaining = [c for c in existing if c.doc_id != doc_id]
    removed = len(existing) - len(remaining)
    if removed > 0:
        build_index(remaining, settings=settings)
        logger.info("BM25: removed %d chunks (doc_id=%s), %d remain", removed, doc_id, len(remaining))
    return removed
