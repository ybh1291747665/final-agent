from __future__ import annotations


def test_build_index_for_course_writes_course_snapshot(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, course_index_path
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    chunks = [
        Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation testing"),
        Chunk(chunk_id="a2", doc_id="doc-a", course_id="course-a", text="branching strategy"),
    ]

    count = build_index_for_course("course-a", chunks, settings=settings)

    assert count == 2
    assert course_index_path("course-a", settings).exists()


def test_ensure_course_loaded_switches_sparse_cache(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, ensure_course_loaded, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    build_index_for_course(
        "course-a",
        [Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation testing")],
        settings=settings,
    )
    build_index_for_course(
        "course-b",
        [Chunk(chunk_id="b1", doc_id="doc-b", course_id="course-b", text="database indexing")],
        settings=settings,
    )

    ensure_course_loaded("course-b", settings=settings)
    results = search("database", top_k=5, course_ids=["course-b"])

    assert [chunk.chunk_id for chunk, _ in results] == ["b1"]
