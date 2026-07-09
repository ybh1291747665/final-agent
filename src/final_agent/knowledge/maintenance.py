"""Course knowledge base maintenance helpers."""

from __future__ import annotations

from final_agent.knowledge.bm25_index import build_index_for_course, course_index_path
from final_agent.knowledge.vector_store import get_chunks_by_course, migrate_legacy_course_collection
from final_agent.settings import Settings, load_settings

_DEFAULT_COURSE_ID = "默认课程"


def rebuild_course_knowledge(
    course_id: str,
    settings: Settings | None = None,
) -> dict[str, int | str]:
    """Repair one course knowledge base from current stored chunks.

    This copies legacy dense chunks into the course collection, then rebuilds the
    course BM25 snapshot from the merged course chunk view.
    """
    if settings is None:
        settings = load_settings()

    normalized_course = course_id or _DEFAULT_COURSE_ID
    migration = migrate_legacy_course_collection(normalized_course, settings=settings)
    scoped_chunks = get_chunks_by_course(normalized_course, settings=settings)
    rebuilt = build_index_for_course(normalized_course, scoped_chunks, settings=settings)

    return {
        "course_id": normalized_course,
        "legacy_chunks": int(migration["legacy_chunks"]),
        "migrated_chunks": int(migration["migrated_chunks"]),
        "skipped_existing": int(migration["skipped_existing"]),
        "sparse_rebuilt_chunks": rebuilt,
        "bm25_snapshot_path": str(course_index_path(normalized_course, settings)),
    }
