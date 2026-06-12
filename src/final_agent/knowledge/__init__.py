"""Knowledge base: embedding, vector store, BM25 index, and metadata."""

from final_agent.knowledge.builder import build
from final_agent.knowledge.embedder import embed_chunks, embed_texts
from final_agent.knowledge.vector_store import query as chroma_query, count as chroma_count, delete_by_doc_id as chroma_delete_doc, get_chunks_by_doc as chroma_get_chunks, get_all_chunks as chroma_get_all
from final_agent.knowledge.bm25_index import search as bm25_search, load_index as bm25_load, delete_by_doc_id as bm25_delete_doc
from final_agent.knowledge.metadata import list_documents, total_chunks as metadata_total, remove_document, list_courses

__all__ = [
    "build",
    "embed_chunks",
    "embed_texts",
    "chroma_query",
    "chroma_count",
    "chroma_delete_doc",
    "chroma_get_chunks",
    "chroma_get_all",
    "bm25_search",
    "bm25_load",
    "bm25_delete_doc",
    "list_documents",
    "metadata_total",
    "remove_document",
    "list_courses",
]
