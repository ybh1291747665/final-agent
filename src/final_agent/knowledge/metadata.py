"""Document metadata — track sources, import times, and chunk counts."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_METADATA_CACHE: Optional[dict] = None
_METADATA_CACHE_PATH: Optional[Path] = None


def _metadata_path(settings: Settings) -> Path:
    return Path(settings.vector_store.persist_dir) / "metadata.json"


def _load(settings: Settings) -> dict:
    global _METADATA_CACHE, _METADATA_CACHE_PATH
    path = _metadata_path(settings).resolve()
    if _METADATA_CACHE is not None and _METADATA_CACHE_PATH == path:
        return _METADATA_CACHE
    if path.exists():
        _METADATA_CACHE = json.loads(path.read_text(encoding="utf-8"))
        _METADATA_CACHE.setdefault("documents", {})
        _METADATA_CACHE.setdefault("courses", [])
    else:
        _METADATA_CACHE = {"documents": {}, "courses": []}
    _METADATA_CACHE_PATH = path
    return _METADATA_CACHE


def _save(settings: Settings) -> None:
    global _METADATA_CACHE_PATH
    if _METADATA_CACHE is None:
        return
    path = _metadata_path(settings).resolve()
    _METADATA_CACHE_PATH = path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_METADATA_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")


def register_document(
    doc_id: str,
    source_path: str,
    chunk_count: int,
    settings: Settings | None = None,
    *,
    course_id: str = "",
    bm25_snapshot_path: str = "",
    content_signature: str = "",
) -> None:
    """Record a document in the metadata store."""
    if settings is None:
        settings = load_settings()
    data = _load(settings)
    normalized_course = course_id or "默认课程"
    data["documents"][doc_id] = {
        "source_path": str(source_path),
        "chunk_count": chunk_count,
        "course_id": normalized_course,
        "imported_at": datetime.now().isoformat(),
        "bm25_snapshot_path": bm25_snapshot_path,
        "content_signature": content_signature,
    }
    _save(settings)
    logger.info("Metadata: registered doc_id=%s (%d chunks)", doc_id, chunk_count)


def remove_document(
    doc_id: str,
    settings: Settings | None = None,
) -> bool:
    """Remove a document from metadata. Returns True if it existed."""
    if settings is None:
        settings = load_settings()
    data = _load(settings)
    existed = doc_id in data.get("documents", {})
    if existed:
        del data["documents"][doc_id]
        _save(settings)
        logger.info("Metadata: removed doc_id=%s", doc_id)
    return existed


def list_documents(settings: Settings | None = None) -> dict:
    """Return {doc_id: {source_path, chunk_count, imported_at}}."""
    if settings is None:
        settings = load_settings()
    return dict(_load(settings).get("documents", {}))


def total_chunks(settings: Settings | None = None) -> int:
    """Sum of chunk counts across all registered documents."""
    if settings is None:
        settings = load_settings()
    return sum(d.get("chunk_count", 0) for d in list_documents(settings).values())


def list_courses(settings: Settings | None = None) -> list[str]:
    """Return distinct course IDs from registered documents."""
    if settings is None:
        settings = load_settings()
    data = _load(settings)
    courses: set[str] = {course for course in data.get("courses", []) if course}
    for info in list_documents(settings).values():
        cid = info.get("course_id", "默认课程")
        if cid:
            courses.add(cid)
    return sorted(courses)


def create_course(course_id: str, settings: Settings | None = None) -> bool:
    """Create an empty course so it can be selected before documents exist."""
    if settings is None:
        settings = load_settings()
    normalized = course_id.strip()
    if not normalized:
        raise ValueError("course_id must not be empty")
    data = _load(settings)
    courses = set(data.setdefault("courses", []))
    if normalized in courses:
        return False
    courses.add(normalized)
    data["courses"] = sorted(courses)
    _save(settings)
    return True


def delete_empty_course(course_id: str, settings: Settings | None = None) -> bool:
    """Delete an explicitly-created course only when no documents belong to it."""
    if settings is None:
        settings = load_settings()
    normalized = course_id.strip()
    if not normalized:
        return False
    data = _load(settings)
    has_documents = any(
        info.get("course_id", "默认课程") == normalized
        for info in data.get("documents", {}).values()
    )
    if has_documents:
        return False
    courses = set(data.setdefault("courses", []))
    if normalized not in courses:
        return False
    courses.remove(normalized)
    data["courses"] = sorted(courses)
    _save(settings)
    return True


def list_course_index_info(settings: Settings | None = None) -> dict[str, dict]:
    """Return aggregated metadata for each course."""
    if settings is None:
        settings = load_settings()
    data = _load(settings)
    grouped: dict[str, dict] = {
        course_id: {
            "chunk_count": 0,
            "doc_ids": [],
            "bm25_snapshot_path": "",
        }
        for course_id in data.get("courses", [])
        if course_id
    }
    for doc_id, info in list_documents(settings).items():
        course_id = info.get("course_id", "默认课程")
        bucket = grouped.setdefault(
            course_id,
            {
                "chunk_count": 0,
                "doc_ids": [],
                "bm25_snapshot_path": info.get("bm25_snapshot_path", ""),
            },
        )
        bucket["chunk_count"] += int(info.get("chunk_count", 0))
        bucket["doc_ids"].append(doc_id)
        if not bucket["bm25_snapshot_path"]:
            bucket["bm25_snapshot_path"] = info.get("bm25_snapshot_path", "")
    for course_id in grouped:
        grouped[course_id]["doc_ids"].sort()
    return grouped
