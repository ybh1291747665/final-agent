from __future__ import annotations

import json


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
    path = course_index_path("course-a", settings)
    assert path.exists()
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["chunk_ids"] == ["a1", "a2"]
    assert [chunk["chunk_id"] for chunk in persisted["chunks"]] == ["a1", "a2"]


def test_ensure_course_loaded_switches_sparse_cache(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, ensure_course_loaded, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    course_a_chunks = [
        Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation testing"),
    ]
    course_b_chunks = [
        Chunk(chunk_id="b1", doc_id="doc-b", course_id="course-b", text="database indexing"),
    ]
    build_index_for_course(
        "course-a",
        course_a_chunks,
        settings=settings,
    )
    build_index_for_course(
        "course-b",
        course_b_chunks,
        settings=settings,
    )
    build_index_for_course("course-a", course_a_chunks, settings=settings)

    active_a_results = search("automation", top_k=5, course_ids=["course-a"])
    assert [chunk.chunk_id for chunk, _ in active_a_results] == ["a1"]

    count = ensure_course_loaded("course-b", settings=settings)
    results = search("database", top_k=5, course_ids=["course-b"])
    stale_results = search("automation", top_k=5, course_ids=["course-a"])

    assert count == 1
    assert [chunk.chunk_id for chunk, _ in results] == ["b1"]
    assert stale_results == []
