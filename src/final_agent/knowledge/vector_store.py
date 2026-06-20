"""ChromaDB vector store — add, query, delete chunks by dense vectors."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
try:
    import chromadb
    from chromadb.api.types import QueryResult
except ModuleNotFoundError:
    chromadb = None  # type: ignore[assignment]
    QueryResult = dict  # type: ignore[assignment]

from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_CLIENT_CACHE: Optional[Any] = None


def _get_client(settings: Settings):
    global _CLIENT_CACHE
    if chromadb is None:
        raise RuntimeError("chromadb is not installed; install project dependencies to use the vector store.")
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE
    persist_dir = settings.vector_store.persist_dir
    logger.info("Initialising ChromaDB at %s", persist_dir)
    _CLIENT_CACHE = chromadb.PersistentClient(path=persist_dir)
    return _CLIENT_CACHE


def _get_collection(
    settings: Settings, client
):
    name = settings.vector_store.collection_name
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(
    chunks: list[tuple[Chunk, np.ndarray]],
    settings: Settings | None = None,
) -> int:
    """Insert chunk-vector pairs into the Chroma collection.

    Args:
        chunks: List of ``(Chunk, vector)`` pairs.
        settings: Application settings.

    Returns:
        Number of chunks added.
    """
    if not chunks:
        return 0
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    col = _get_collection(settings, client)

    ids = [c.chunk_id for c, _ in chunks]
    embeddings = [v.tolist() for _, v in chunks]
    documents = [c.text for c, _ in chunks]
    metadatas = [
        {
            "doc_id": c.doc_id,
            "course_id": c.course_id or "",
            "heading_path": "/".join(c.heading_path),
            "char_start": c.char_start,
            "char_end": c.char_end,
            "page_num": c.page_num or 0,
        }
        for c, _ in chunks
    ]

    col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    logger.info("Added %d chunks to Chroma collection '%s'", len(chunks), col.name)
    return len(chunks)


def query(
    query_vector: np.ndarray,
    top_k: int = 10,
    settings: Settings | None = None,
    *,
    course_ids: list[str] | None = None,
) -> list[tuple[Chunk, float]]:
    """Retrieve the *top_k* most similar chunks for a query vector.

    Args:
        query_vector: 1-d float32 embedding of the query.
        top_k: Number of results.
        settings: Application settings.
        course_ids: Optional list of course_ids to filter by.

    Returns:
        List of ``(Chunk, cosine_similarity)`` pairs, best first.
    """
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    col = _get_collection(settings, client)

    kwargs: dict = {
        "query_embeddings": [query_vector.tolist()],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if course_ids and course_ids[0]:
        # Build where clause: match doc_ids belonging to any of the given courses.
        # We need to first find which doc_ids belong to those courses.
        from final_agent.knowledge.metadata import list_documents as _list_docs
        docs = _list_docs(settings=settings)
        target_doc_ids = [
            d_id for d_id, info in docs.items()
            if info.get("course_id", "默认课程") in course_ids
        ]
        if target_doc_ids:
            kwargs["where"] = {"doc_id": {"$in": target_doc_ids}}

    result: QueryResult = col.query(**kwargs)

    chunks: list[tuple[Chunk, float]] = []
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for i in range(len(ids)):
        heading_raw = (metas[i] or {}).get("heading_path", "")
        heading_path = heading_raw.split("/") if heading_raw else []
        chunk = Chunk(
            chunk_id=ids[i],
            doc_id=(metas[i] or {}).get("doc_id", ""),
            course_id=(metas[i] or {}).get("course_id", ""),
            text=docs[i] if i < len(docs) else "",
            heading_path=heading_path,
            page_num=(metas[i] or {}).get("page_num") or None,
            char_start=(metas[i] or {}).get("char_start", 0),
            char_end=(metas[i] or {}).get("char_end", 0),
        )
        # Chroma with cosine space: distance = 1 - cosine_similarity
        sim = 1.0 - distances[i] if distances else 0.0
        chunks.append((chunk, sim))

    return chunks


def delete_by_doc_id(
    doc_id: str,
    settings: Settings | None = None,
) -> int:
    """Remove all chunks belonging to *doc_id*."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    col = _get_collection(settings, client)
    # Chroma doesn't support delete by metadata filter in all versions;
    # fall back to get-then-delete.
    existing = col.get(where={"doc_id": doc_id})
    if existing and existing.get("ids"):
        ids = existing["ids"]
        col.delete(ids=ids)
        logger.info("Deleted %d chunks for doc_id=%s", len(ids), doc_id)
        return len(ids)
    return 0


def count(settings: Settings | None = None) -> int:
    """Return total number of chunks in the collection."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    col = _get_collection(settings, client)
    return col.count()


def get_chunks_by_doc(
    doc_id: str,
    settings: Settings | None = None,
) -> list[Chunk]:
    """Retrieve all chunks for a document."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    col = _get_collection(settings, client)
    existing = col.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
    chunks: list[Chunk] = []
    if not existing or not existing.get("ids"):
        return chunks
    for i, cid in enumerate(existing["ids"]):
        meta = (existing["metadatas"] or [{}])[i] if i < len(existing.get("metadatas") or []) else {}
        heading_raw = meta.get("heading_path", "")
        chunks.append(Chunk(
            chunk_id=cid,
            doc_id=doc_id,
            course_id=meta.get("course_id", ""),
            text=(existing["documents"] or [""])[i] if i < len(existing.get("documents") or []) else "",
            heading_path=heading_raw.split("/") if heading_raw else [],
            page_num=meta.get("page_num") or None,
            char_start=meta.get("char_start", 0),
            char_end=meta.get("char_end", 0),
        ))
    return chunks


def get_all_chunks(
    settings: Settings | None = None,
) -> list[Chunk]:
    """Retrieve every chunk in the Chroma collection (for BM25 restoration)."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    col = _get_collection(settings, client)
    # Fetch all with a large limit — Chroma's get() without where returns everything
    existing = col.get(include=["documents", "metadatas"])
    chunks: list[Chunk] = []
    if not existing or not existing.get("ids"):
        return chunks
    for i, cid in enumerate(existing["ids"]):
        meta = (existing["metadatas"] or [{}])[i] if i < len(existing.get("metadatas") or []) else {}
        heading_raw = meta.get("heading_path", "")
        chunks.append(Chunk(
            chunk_id=cid,
            doc_id=meta.get("doc_id", ""),
            course_id=meta.get("course_id", ""),
            text=(existing["documents"] or [""])[i] if i < len(existing.get("documents") or []) else "",
            heading_path=heading_raw.split("/") if heading_raw else [],
            page_num=meta.get("page_num") or None,
            char_start=meta.get("char_start", 0),
            char_end=meta.get("char_end", 0),
        ))
    return chunks
