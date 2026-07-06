"""ChromaDB vector store — add, query, delete chunks by dense vectors."""

from __future__ import annotations

import logging
import hashlib
import re
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
_DEFAULT_COURSE_KEY = "默认课程"


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


def _course_key(course_id: str) -> str:
    return course_id or _DEFAULT_COURSE_KEY


def _course_slug(course_id: str) -> str:
    normalized = _course_key(course_id)
    if normalized == _DEFAULT_COURSE_KEY:
        return "default"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", normalized).strip("-._")
    return slug or "course"


def course_collection_name(course_id: str, settings: Settings | None = None) -> str:
    if settings is None:
        settings = load_settings()
    normalized = _course_key(course_id)
    slug = _course_slug(course_id)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    base_name = re.sub(r"[^A-Za-z0-9._-]+", "-", settings.vector_store.collection_name).strip("-._")
    base_name = base_name or "final-agent"
    return f"{base_name}_course_{slug}_{digest}"


def _get_collection(
    settings: Settings, client, course_id: str = ""
):
    name = course_collection_name(course_id, settings=settings)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _get_legacy_collection(settings: Settings, client):
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", settings.vector_store.collection_name).strip("-._")
    name = name or "final-agent"
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _list_registered_course_ids(settings: Settings) -> list[str]:
    from final_agent.knowledge.metadata import list_course_index_info

    return list(list_course_index_info(settings).keys())


def _doc_ids_for_course(course_id: str, settings: Settings) -> list[str]:
    from final_agent.knowledge.metadata import list_documents

    normalized_course = _course_key(course_id)
    docs = list_documents(settings=settings)
    return [
        doc_id
        for doc_id, info in docs.items()
        if _course_key(info.get("course_id", "")) == normalized_course
    ]


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
    grouped: dict[str, list[tuple[Chunk, np.ndarray]]] = {}
    for chunk, vector in chunks:
        grouped.setdefault(_course_key(chunk.course_id), []).append((chunk, vector))

    for course_id, scoped_chunks in grouped.items():
        col = _get_collection(settings, client, course_id)
        ids = [c.chunk_id for c, _ in scoped_chunks]
        embeddings = [v.tolist() for _, v in scoped_chunks]
        documents = [c.text for c, _ in scoped_chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "course_id": _course_key(c.course_id),
                "heading_path": "/".join(c.heading_path),
                "char_start": c.char_start,
                "char_end": c.char_end,
                "page_num": c.page_num or 0,
            }
            for c, _ in scoped_chunks
        ]

        col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        logger.info("Added %d chunks to Chroma collection '%s'", len(scoped_chunks), col.name)
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

    scoped_course_ids = [course_id for course_id in (course_ids or []) if course_id]
    if not scoped_course_ids:
        scoped_course_ids = _list_registered_course_ids(settings)
    if not scoped_course_ids:
        scoped_course_ids = [_DEFAULT_COURSE_KEY]

    merged: list[tuple[Chunk, float]] = []
    seen_chunk_ids: set[str] = set()
    per_course_top_k = top_k if len(scoped_course_ids) == 1 else max(top_k, 10)
    for course_id in scoped_course_ids:
        col = _get_collection(settings, client, course_id)
        for chunk, score in _query_collection(col, query_vector, per_course_top_k):
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            merged.append((chunk, score))
        legacy_doc_ids = _doc_ids_for_course(course_id, settings)
        if legacy_doc_ids:
            legacy_col = _get_legacy_collection(settings, client)
            legacy_where = {"doc_id": {"$in": legacy_doc_ids}}
            for chunk, score in _query_collection(legacy_col, query_vector, per_course_top_k, where=legacy_where):
                if chunk.chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.chunk_id)
                merged.append((chunk, score))

    return sorted(merged, key=lambda item: item[1], reverse=True)[:top_k]


def _query_collection(
    col,
    query_vector: np.ndarray,
    top_k: int,
    *,
    where: dict | None = None,
) -> list[tuple[Chunk, float]]:
    kwargs: dict = {
        "query_embeddings": [query_vector.tolist()],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

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
    from final_agent.knowledge.metadata import list_documents as _list_docs

    docs = _list_docs(settings=settings)
    course_id = _course_key(docs.get(doc_id, {}).get("course_id", ""))
    col = _get_collection(settings, client, course_id)
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
    total = 0
    for course_id in _list_registered_course_ids(settings) or [_DEFAULT_COURSE_KEY]:
        col = _get_collection(settings, client, course_id)
        total += col.count()
    return total


def get_chunks_by_doc(
    doc_id: str,
    settings: Settings | None = None,
) -> list[Chunk]:
    """Retrieve all chunks for a document."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    from final_agent.knowledge.metadata import list_documents as _list_docs

    docs = _list_docs(settings=settings)
    course_id = _course_key(docs.get(doc_id, {}).get("course_id", ""))
    col = _get_collection(settings, client, course_id)
    existing = col.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
    chunks = _chunks_from_get_result(existing, fallback_doc_id=doc_id)
    if not chunks:
        legacy_col = _get_legacy_collection(settings, client)
        legacy_existing = legacy_col.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
        chunks = _chunks_from_get_result(legacy_existing, fallback_doc_id=doc_id)
    return chunks


def get_chunks_by_course(
    course_id: str,
    settings: Settings | None = None,
) -> list[Chunk]:
    """Retrieve all chunks for one course without scanning unrelated courses."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    normalized_course = course_id or "默认课程"
    col = _get_collection(settings, client, normalized_course)
    existing = col.get(where={"course_id": normalized_course}, include=["documents", "metadatas"])
    chunks = _chunks_from_get_result(existing)
    seen_chunk_ids = {chunk.chunk_id for chunk in chunks}
    legacy_doc_ids = _doc_ids_for_course(normalized_course, settings)
    if legacy_doc_ids:
        legacy_col = _get_legacy_collection(settings, client)
        legacy_existing = legacy_col.get(where={"doc_id": {"$in": legacy_doc_ids}}, include=["documents", "metadatas"])
        for chunk in _chunks_from_get_result(legacy_existing):
            if chunk.chunk_id not in seen_chunk_ids:
                chunks.append(chunk)
                seen_chunk_ids.add(chunk.chunk_id)
    return chunks


def _chunks_from_get_result(existing, *, fallback_doc_id: str = "") -> list[Chunk]:
    chunks: list[Chunk] = []
    if not existing or not existing.get("ids"):
        return chunks
    for i, cid in enumerate(existing["ids"]):
        meta = (existing["metadatas"] or [{}])[i] if i < len(existing.get("metadatas") or []) else {}
        heading_raw = meta.get("heading_path", "")
        chunks.append(Chunk(
            chunk_id=cid,
            doc_id=meta.get("doc_id", fallback_doc_id),
            course_id=meta.get("course_id", ""),
            text=(existing["documents"] or [""])[i] if i < len(existing.get("documents") or []) else "",
            heading_path=heading_raw.split("/") if heading_raw else [],
            page_num=meta.get("page_num") or None,
            char_start=meta.get("char_start", 0),
            char_end=meta.get("char_end", 0),
        ))
    return chunks


def migrate_legacy_course_collection(
    course_id: str,
    settings: Settings | None = None,
) -> dict[str, int | str]:
    """Copy legacy global Chroma chunks for one course into its course collection.

    This is intentionally non-destructive: the legacy collection is left intact
    until a separate cleanup step is chosen.
    """
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    normalized_course = _course_key(course_id)
    doc_ids = _doc_ids_for_course(normalized_course, settings)
    if not doc_ids:
        return {
            "course_id": normalized_course,
            "legacy_chunks": 0,
            "migrated_chunks": 0,
            "skipped_existing": 0,
        }

    legacy_col = _get_legacy_collection(settings, client)
    target_col = _get_collection(settings, client, normalized_course)
    legacy = legacy_col.get(
        where={"doc_id": {"$in": doc_ids}},
        include=["documents", "metadatas", "embeddings"],
    )
    legacy_ids = legacy.get("ids", []) if legacy else []
    if not legacy_ids:
        return {
            "course_id": normalized_course,
            "legacy_chunks": 0,
            "migrated_chunks": 0,
            "skipped_existing": 0,
        }

    existing = target_col.get(where={"doc_id": {"$in": doc_ids}})
    existing_ids = set(existing.get("ids", []) if existing else [])
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    embeddings: list[list[float]] = []
    legacy_embeddings = legacy.get("embeddings")
    if legacy_embeddings is None:
        legacy_embeddings = []
    legacy_documents = legacy.get("documents")
    if legacy_documents is None:
        legacy_documents = []
    legacy_metadatas = legacy.get("metadatas")
    if legacy_metadatas is None:
        legacy_metadatas = []

    for index, chunk_id in enumerate(legacy_ids):
        if chunk_id in existing_ids:
            continue
        if index >= len(legacy_embeddings):
            continue
        meta = dict(legacy_metadatas[index] if index < len(legacy_metadatas) else {})
        meta["course_id"] = _course_key(meta.get("course_id", normalized_course))
        ids.append(chunk_id)
        documents.append(legacy_documents[index] if index < len(legacy_documents) else "")
        metadatas.append(meta)
        embedding = legacy_embeddings[index]
        embeddings.append(embedding.tolist() if hasattr(embedding, "tolist") else embedding)

    if ids:
        target_col.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    return {
        "course_id": normalized_course,
        "legacy_chunks": len(legacy_ids),
        "migrated_chunks": len(ids),
        "skipped_existing": len(legacy_ids) - len(ids),
    }


def get_all_chunks(
    settings: Settings | None = None,
) -> list[Chunk]:
    """Retrieve every chunk in the Chroma collection (for BM25 restoration)."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)
    chunks: list[Chunk] = []
    for course_id in _list_registered_course_ids(settings) or [_DEFAULT_COURSE_KEY]:
        col = _get_collection(settings, client, course_id)
        existing = col.get(include=["documents", "metadatas"])
        if not existing or not existing.get("ids"):
            continue
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
