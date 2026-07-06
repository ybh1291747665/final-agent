"""Knowledge base: embedding, vector store, BM25 index, and metadata."""

from final_agent.knowledge.builder import build
from final_agent.knowledge.embedder import embed_chunks, embed_texts
from final_agent.knowledge.vector_store import (
    count as chroma_count,
    delete_by_doc_id as chroma_delete_doc,
    get_all_chunks as chroma_get_all,
    get_chunks_by_course as chroma_get_course_chunks,
    get_chunks_by_doc as chroma_get_chunks,
    migrate_legacy_course_collection as chroma_migrate_legacy_course,
    query as chroma_query,
)
from final_agent.knowledge.bm25_index import (
    build_index as build_index,
    build_index_for_course,
    course_index_path,
    ensure_course_loaded,
    search as bm25_search,
    load_index as bm25_load,
    delete_by_doc_id as bm25_delete_doc,
)
from final_agent.knowledge.metadata import (
    create_course,
    list_course_index_info,
    list_courses,
    list_documents,
    remove_document,
    total_chunks as metadata_total,
)

__all__ = [
    "build",
    "embed_chunks",
    "embed_texts",
    "chroma_query",
    "chroma_count",
    "chroma_delete_doc",
    "chroma_get_chunks",
    "chroma_get_course_chunks",
    "chroma_get_all",
    "chroma_migrate_legacy_course",
    "build_index",
    "build_index_for_course",
    "course_index_path",
    "ensure_course_loaded",
    "bm25_search",
    "bm25_load",
    "bm25_delete_doc",
    "list_documents",
    "create_course",
    "list_course_index_info",
    "metadata_total",
    "remove_document",
    "list_courses",
]
