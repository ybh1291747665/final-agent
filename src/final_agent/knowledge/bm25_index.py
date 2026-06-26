"""BM25 sparse index with jieba tokenisation and JSON persistence."""

from __future__ import annotations

import hashlib
import json
import logging
import re
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
_ACTIVE_COURSE_ID: Optional[str] = None
_ACTIVE_SNAPSHOT_PATH: Optional[Path] = None
_DEFAULT_COURSE_KEY = "\u9ed8\u8ba4\u8bfe\u7a0b"


def _bm25_index_path(settings: Settings) -> Path:
    return Path(settings.vector_store.persist_dir) / "bm25_index.json"


def _course_key(course_id: str) -> str:
    return course_id or _DEFAULT_COURSE_KEY


def _course_slug(course_id: str) -> str:
    normalized = _course_key(course_id)
    if normalized == _DEFAULT_COURSE_KEY:
        return "default"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", normalized).strip("-._")
    return slug or "course"


def course_index_path(course_id: str, settings: Settings) -> Path:
    normalized = _course_key(course_id)
    slug = _course_slug(course_id)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    return Path(settings.vector_store.persist_dir) / f"bm25_{slug}_{digest}.json"


def _snapshot_payload(chunks: list[Chunk]) -> dict[str, object]:
    return {
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
        "chunks": [chunk.model_dump() for chunk in chunks],
    }


def _restore_snapshot_chunks(data: dict[str, object]) -> list[Chunk]:
    raw_chunks = data.get("chunks", [])
    if not isinstance(raw_chunks, list):
        return []

    restored: list[Chunk] = []
    for raw_chunk in raw_chunks:
        if isinstance(raw_chunk, dict):
            restored.append(Chunk.model_validate(raw_chunk))
    return restored


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
        return [t for t in re.split(r"\W+", text.lower()) if t]


def build_index(
    chunks: list[Chunk],
    settings: Settings | None = None,
) -> int:
    """Build (or rebuild) the BM25 index from all chunks and persist to JSON."""
    global _INDEX_CACHE, _CHUNK_MAP_CACHE, _ACTIVE_COURSE_ID, _ACTIVE_SNAPSHOT_PATH
    if settings is None:
        settings = load_settings()

    if not chunks:
        _INDEX_CACHE = None
        _CHUNK_MAP_CACHE = None
        _ACTIVE_COURSE_ID = None
        _ACTIVE_SNAPSHOT_PATH = None
        path = _bm25_index_path(settings)
        if path.exists():
            path.unlink()
        return 0

    tokenized = [_tokenize(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(tokenized)
    _INDEX_CACHE = bm25
    _CHUNK_MAP_CACHE = list(chunks)
    _ACTIVE_COURSE_ID = None
    _ACTIVE_SNAPSHOT_PATH = None

    data = {
        "corpus_size": bm25.corpus_size,
        "doc_len": bm25.doc_len,
        "doc_freqs": bm25.doc_freqs,
        "idf": bm25.idf,
        "avgdl": bm25.avgdl,
        "k1": bm25.k1,
        "b": bm25.b,
        "epsilon": bm25.epsilon,
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
    }
    path = _bm25_index_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("BM25 index built: %d chunks -> %s", len(chunks), path)
    return len(chunks)


def build_index_for_course(
    course_id: str,
    chunks: list[Chunk],
    settings: Settings | None = None,
) -> int:
    global _INDEX_CACHE, _CHUNK_MAP_CACHE, _ACTIVE_COURSE_ID, _ACTIVE_SNAPSHOT_PATH
    if settings is None:
        settings = load_settings()

    path = course_index_path(course_id, settings)
    snapshot_path = path.resolve()
    normalized_course = _course_key(course_id)
    scoped = [chunk for chunk in chunks if _course_key(chunk.course_id) == normalized_course]

    if not scoped:
        if path.exists():
            path.unlink()
        if _ACTIVE_COURSE_ID == normalized_course and _ACTIVE_SNAPSHOT_PATH == snapshot_path:
            _INDEX_CACHE = None
            _CHUNK_MAP_CACHE = None
            _ACTIVE_COURSE_ID = None
            _ACTIVE_SNAPSHOT_PATH = None
        return 0

    tokenized = [_tokenize(chunk.text) for chunk in scoped]
    _INDEX_CACHE = BM25Okapi(tokenized)
    _CHUNK_MAP_CACHE = scoped
    _ACTIVE_COURSE_ID = normalized_course
    _ACTIVE_SNAPSHOT_PATH = snapshot_path

    data = _snapshot_payload(scoped)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("BM25 course index built: %s -> %d chunks", course_id, len(scoped))
    return len(scoped)


def load_index(
    chunks: list[Chunk],
    settings: Settings | None = None,
) -> int:
    """Restore BM25 index from JSON. Falls back to build_index if missing."""
    global _INDEX_CACHE, _CHUNK_MAP_CACHE, _ACTIVE_COURSE_ID, _ACTIVE_SNAPSHOT_PATH
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
    resolved = [chunk for chunk in chunks if chunk.chunk_id in persisted_ids]
    if not resolved:
        return build_index(chunks, settings)

    tokenized = [_tokenize(chunk.text) for chunk in resolved]
    _INDEX_CACHE = BM25Okapi(tokenized)
    _CHUNK_MAP_CACHE = resolved
    _ACTIVE_COURSE_ID = None
    _ACTIVE_SNAPSHOT_PATH = None

    logger.info("BM25 index loaded: %d chunks from %s", len(resolved), path)
    return len(resolved)


def ensure_course_loaded(
    course_id: str,
    *,
    settings: Settings | None = None,
    chunks: list[Chunk] | None = None,
) -> int:
    global _INDEX_CACHE, _CHUNK_MAP_CACHE, _ACTIVE_COURSE_ID, _ACTIVE_SNAPSHOT_PATH
    if settings is None:
        settings = load_settings()

    scoped_chunks = list(chunks or [])
    path = course_index_path(course_id, settings)
    snapshot_path = path.resolve()
    normalized_course = _course_key(course_id)
    if (
        _ACTIVE_COURSE_ID == normalized_course
        and _ACTIVE_SNAPSHOT_PATH == snapshot_path
        and _INDEX_CACHE is not None
        and _CHUNK_MAP_CACHE is not None
    ):
        return len(_CHUNK_MAP_CACHE)

    if not path.exists():
        return build_index_for_course(course_id, scoped_chunks, settings=settings)

    try:
        persisted = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return build_index_for_course(course_id, scoped_chunks, settings=settings)

    allowed_ids = set(persisted.get("chunk_ids", []))
    provided = [chunk for chunk in scoped_chunks if chunk.chunk_id in allowed_ids]
    if allowed_ids and {chunk.chunk_id for chunk in provided} == allowed_ids:
        resolved = provided
    else:
        resolved = _restore_snapshot_chunks(persisted)
    if not resolved:
        return build_index_for_course(course_id, scoped_chunks, settings=settings)

    tokenized = [_tokenize(chunk.text) for chunk in resolved]
    _INDEX_CACHE = BM25Okapi(tokenized)
    _CHUNK_MAP_CACHE = resolved
    _ACTIVE_COURSE_ID = normalized_course
    _ACTIVE_SNAPSHOT_PATH = snapshot_path
    logger.info("BM25 course index loaded: %s -> %d chunks", course_id, len(resolved))
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
    token_set = set(tokens)
    scores = _INDEX_CACHE.get_scores(tokens)
    top_indices = np.argsort(scores)[::-1]
    use_overlap_fallback = len(_CHUNK_MAP_CACHE) == 1
    results: list[tuple[Chunk, float]] = []
    for idx in top_indices:
        if idx >= len(_CHUNK_MAP_CACHE):
            continue
        chunk = _CHUNK_MAP_CACHE[idx]
        overlap = len(token_set.intersection(_tokenize(chunk.text)))
        if scores[idx] <= 0:
            if not use_overlap_fallback or overlap <= 0:
                continue
            score = float(overlap)
        else:
            score = float(scores[idx])
        if course_ids and course_ids[0] and chunk.course_id not in course_ids:
            continue
        results.append((chunk, score))
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
    """Remove chunks with doc_id from BM25 index and rebuild."""
    global _INDEX_CACHE, _CHUNK_MAP_CACHE, _ACTIVE_COURSE_ID
    if settings is None:
        settings = load_settings()
    existing = get_cached_chunks()
    remaining = [chunk for chunk in existing if chunk.doc_id != doc_id]
    removed = len(existing) - len(remaining)
    if removed > 0:
        if _ACTIVE_COURSE_ID is None:
            build_index(remaining, settings=settings)
        else:
            build_index_for_course(_ACTIVE_COURSE_ID, remaining, settings=settings)
        logger.info("BM25: removed %d chunks (doc_id=%s), %d remain", removed, doc_id, len(remaining))
    return removed
