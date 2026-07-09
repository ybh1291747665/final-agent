from __future__ import annotations


def test_rebuild_course_knowledge_migrates_dense_and_rebuilds_sparse(monkeypatch, tmp_path):
    from final_agent.knowledge import maintenance
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    chunks = [
        Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation"),
        Chunk(chunk_id="a2", doc_id="doc-a", course_id="course-a", text="testing"),
    ]
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        maintenance,
        "migrate_legacy_course_collection",
        lambda course_id, *, settings: {
            "course_id": course_id,
            "legacy_chunks": 3,
            "migrated_chunks": 1,
            "skipped_existing": 2,
        },
    )
    monkeypatch.setattr(
        maintenance,
        "get_chunks_by_course",
        lambda course_id, *, settings: chunks,
    )

    def fake_build_index_for_course(course_id, scoped_chunks, *, settings):
        calls["course_id"] = course_id
        calls["chunk_ids"] = [chunk.chunk_id for chunk in scoped_chunks]
        return len(scoped_chunks)

    monkeypatch.setattr(maintenance, "build_index_for_course", fake_build_index_for_course)

    summary = maintenance.rebuild_course_knowledge("course-a", settings=settings)

    assert summary == {
        "course_id": "course-a",
        "legacy_chunks": 3,
        "migrated_chunks": 1,
        "skipped_existing": 2,
        "sparse_rebuilt_chunks": 2,
        "bm25_snapshot_path": str(maintenance.course_index_path("course-a", settings)),
    }
    assert calls == {"course_id": "course-a", "chunk_ids": ["a1", "a2"]}
