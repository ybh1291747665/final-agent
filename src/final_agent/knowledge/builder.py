"""Knowledge builder: embed chunks and refresh per-course indices."""

from __future__ import annotations

import logging

from final_agent.knowledge.bm25_index import build_index_for_course, course_index_path
from final_agent.knowledge.embedder import embed_chunks
from final_agent.knowledge.metadata import register_document
from final_agent.knowledge.vector_store import add_chunks, get_all_chunks
from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_DEFAULT_COURSE_ID = "默认课程"


def build(
    chunks: list[Chunk],
    *,
    source_path: str = "",
    settings: Settings | None = None,
) -> dict:
    """Build the vector store and refresh the sparse index for one course."""
    if settings is None:
        settings = load_settings()

    if not chunks:
        logger.warning("build() called with 0 chunks; nothing to do")
        return {
            "chunks": 0,
            "doc_id": "",
            "course_id": "",
            "bm25_scope_chunks": 0,
        }

    doc_id = chunks[0].doc_id or "unknown"
    course_id = chunks[0].course_id or _DEFAULT_COURSE_ID

    logger.info("Embedding %d chunks...", len(chunks))
    pairs = embed_chunks(chunks, settings=settings)

    add_chunks(pairs, settings=settings)

    all_chunks = get_all_chunks(settings=settings)
    scoped_chunks = [chunk for chunk in all_chunks if (chunk.course_id or _DEFAULT_COURSE_ID) == course_id]
    build_index_for_course(course_id, scoped_chunks, settings=settings)

    register_document(
        doc_id,
        source_path or doc_id,
        len(chunks),
        settings=settings,
        course_id=course_id,
        bm25_snapshot_path=str(course_index_path(course_id, settings)),
    )

    summary = {
        "chunks": len(chunks),
        "doc_id": doc_id,
        "course_id": course_id,
        "bm25_scope_chunks": len(scoped_chunks),
    }
    logger.info("Knowledge base built: %s", summary)
    return summary
