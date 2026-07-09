"""Knowledge builder: embed chunks and refresh per-course indices."""

from __future__ import annotations

import hashlib
import json
import logging

from final_agent.knowledge.bm25_index import build_index_for_course, course_index_path
from final_agent.knowledge.embedder import embed_chunks
from final_agent.knowledge.metadata import list_documents, register_document
from final_agent.knowledge.vector_store import add_chunks, get_chunks_by_course
from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_DEFAULT_COURSE_ID = "默认课程"


def chunk_content_signature(chunks: list[Chunk]) -> str:
    payload = [
        {
            "doc_id": chunk.doc_id,
            "course_id": chunk.course_id,
            "text": chunk.text,
            "heading_path": chunk.heading_path,
            "page_num": chunk.page_num,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        }
        for chunk in chunks
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


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
    content_signature = chunk_content_signature(chunks)
    existing_doc = list_documents(settings=settings).get(doc_id, {})
    if existing_doc.get("content_signature") == content_signature:
        summary = {
            "chunks": len(chunks),
            "doc_id": doc_id,
            "course_id": course_id,
            "bm25_scope_chunks": 0,
            "content_signature": content_signature,
            "skipped": True,
            "skip_reason": "unchanged-document",
        }
        logger.info("Knowledge build skipped: %s", summary)
        return summary

    logger.info("Embedding %d chunks...", len(chunks))
    pairs = embed_chunks(chunks, settings=settings)

    add_chunks(pairs, settings=settings)

    scoped_chunks = get_chunks_by_course(course_id, settings=settings)
    build_index_for_course(course_id, scoped_chunks, settings=settings)

    register_document(
        doc_id,
        source_path or doc_id,
        len(chunks),
        settings=settings,
        course_id=course_id,
        bm25_snapshot_path=str(course_index_path(course_id, settings)),
        content_signature=content_signature,
    )

    summary = {
        "chunks": len(chunks),
        "doc_id": doc_id,
        "course_id": course_id,
        "bm25_scope_chunks": len(scoped_chunks),
        "content_signature": content_signature,
        "skipped": False,
        "skip_reason": "",
    }
    logger.info("Knowledge base built: %s", summary)
    return summary
