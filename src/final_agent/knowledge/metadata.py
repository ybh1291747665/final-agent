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


def _metadata_path(settings: Settings) -> Path:
    return Path(settings.vector_store.persist_dir) / "metadata.json"


def _load(settings: Settings) -> dict:
    global _METADATA_CACHE
    if _METADATA_CACHE is not None:
        return _METADATA_CACHE
    path = _metadata_path(settings)
    if path.exists():
        _METADATA_CACHE = json.loads(path.read_text(encoding="utf-8"))
    else:
        _METADATA_CACHE = {"documents": {}}
    return _METADATA_CACHE


def _save(settings: Settings) -> None:
    if _METADATA_CACHE is None:
        return
    path = _metadata_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_METADATA_CACHE, ensure_ascii=False, indent=2), encoding="utf-8")


def register_document(
    doc_id: str,
    source_path: str,
    chunk_count: int,
    settings: Settings | None = None,
    *,
    course_id: str = "",
) -> None:
    """Record a document in the metadata store."""
    if settings is None:
        settings = load_settings()
    data = _load(settings)
    data["documents"][doc_id] = {
        "source_path": str(source_path),
        "chunk_count": chunk_count,
        "course_id": course_id or "默认课程",
        "imported_at": datetime.now().isoformat(),
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
    courses: set[str] = set()
    for info in list_documents(settings).values():
        cid = info.get("course_id", "默认课程")
        if cid:
            courses.add(cid)
    return sorted(courses)
