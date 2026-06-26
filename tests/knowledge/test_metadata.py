from __future__ import annotations

import json


def test_register_document_tracks_course_snapshot_path(tmp_path):
    from final_agent.knowledge import metadata
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    metadata.register_document(
        "doc-a",
        "course-a/lesson.md",
        3,
        settings=settings,
        course_id="course-a",
        bm25_snapshot_path=str(tmp_path / "bm25_course-a.json"),
    )

    persisted = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert persisted["documents"]["doc-a"]["bm25_snapshot_path"].endswith("bm25_course-a.json")

    metadata._METADATA_CACHE = None
    info = metadata.list_course_index_info(settings)

    assert info["course-a"]["chunk_count"] == 3
    assert info["course-a"]["doc_ids"] == ["doc-a"]
    assert info["course-a"]["bm25_snapshot_path"].endswith("bm25_course-a.json")


def test_remove_document_updates_course_chunk_totals_and_sorts_doc_ids(tmp_path):
    from final_agent.knowledge import metadata
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    metadata.register_document("doc-c", "c.md", 1, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")
    metadata.register_document("doc-a", "a.md", 3, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")
    metadata.register_document("doc-b", "b.md", 2, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")

    metadata._METADATA_CACHE = None
    info = metadata.list_course_index_info(settings)
    assert info["course-a"]["doc_ids"] == ["doc-a", "doc-b", "doc-c"]

    assert metadata.remove_document("doc-a", settings=settings) is True

    metadata._METADATA_CACHE = None
    info = metadata.list_course_index_info(settings)
    assert info["course-a"]["chunk_count"] == 3
    assert info["course-a"]["doc_ids"] == ["doc-b", "doc-c"]
