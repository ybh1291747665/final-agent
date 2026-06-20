"""Knowledge builder — unified entry point: embed chunks and populate all indices."""

from __future__ import annotations

import logging

from final_agent.knowledge.bm25_index import build_index as build_bm25, get_cached_chunks
from final_agent.knowledge.embedder import embed_chunks
from final_agent.knowledge.metadata import register_document
from final_agent.knowledge.vector_store import add_chunks
from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def build(
    chunks: list[Chunk],
    *,
    source_path: str = "",
    settings: Settings | None = None,
) -> dict:
    """Build (or rebuild) the full knowledge base from chunks.

    Pipeline:  embed  →  chroma add  →  bm25 index  →  metadata register

    Args:
        chunks: Ordered list of ``Chunk`` instances.
        source_path: Original source file path (for metadata).
        settings: Application settings.

    Returns:
        Summary dict: ``{"chunks": int, "doc_id": str, "bm25_docs": int}``.
    """
    if settings is None:
        settings = load_settings()

    if not chunks:
        logger.warning("build() called with 0 chunks — nothing to do")
        return {"chunks": 0, "doc_id": "", "bm25_docs": 0}

    doc_id = chunks[0].doc_id or "unknown"

    # 1. Embed
    logger.info("Embedding %d chunks...", len(chunks))
    pairs = embed_chunks(chunks, settings=settings)

    # 2. Chroma
    add_chunks(pairs, settings=settings)

    # 3. BM25 — merge new chunks with existing, then rebuild full index
    existing_bm25 = get_cached_chunks()
    seen_ids = {c.chunk_id for c in existing_bm25}
    all_bm25_chunks = existing_bm25 + [c for c in chunks if c.chunk_id not in seen_ids]
    build_bm25(all_bm25_chunks, settings=settings)

    # 4. Metadata
    src = source_path or doc_id
    course_id = chunks[0].course_id or "默认课程"
    register_document(doc_id, src, len(chunks), settings=settings, course_id=course_id)

    summary = {
        "chunks": len(chunks),
        "doc_id": doc_id,
        "bm25_total": len(all_bm25_chunks),
        "bm25_new": len([c for c in chunks if c.chunk_id not in seen_ids]),
    }
    logger.info("Knowledge base built: %s", summary)
    return summary
