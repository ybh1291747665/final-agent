from __future__ import annotations


def test_register_document_tracks_course_snapshot_path(tmp_path):
    from final_agent.knowledge.metadata import list_course_index_info, register_document
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    register_document(
        "doc-a",
        "course-a/lesson.md",
        3,
        settings=settings,
        course_id="course-a",
        bm25_snapshot_path=str(tmp_path / "bm25_course-a.json"),
    )

    info = list_course_index_info(settings)

    assert info["course-a"]["chunk_count"] == 3
    assert info["course-a"]["doc_ids"] == ["doc-a"]
    assert info["course-a"]["bm25_snapshot_path"].endswith("bm25_course-a.json")


def test_remove_document_updates_course_chunk_totals(tmp_path):
    from final_agent.knowledge.metadata import list_course_index_info, register_document, remove_document
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    register_document("doc-a", "a.md", 3, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")
    register_document("doc-b", "b.md", 2, settings=settings, course_id="course-a", bm25_snapshot_path="bm25_course-a.json")

    assert remove_document("doc-a", settings=settings) is True

    info = list_course_index_info(settings)
    assert info["course-a"]["chunk_count"] == 2
    assert info["course-a"]["doc_ids"] == ["doc-b"]
