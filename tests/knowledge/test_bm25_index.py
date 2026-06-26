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
    build_index_for_course("course-a", course_a_chunks, settings=settings)
    build_index_for_course("course-b", course_b_chunks, settings=settings)
    build_index_for_course("course-a", course_a_chunks, settings=settings)

    active_a_results = search("automation", top_k=5, course_ids=["course-a"])
    assert [chunk.chunk_id for chunk, _ in active_a_results] == ["a1"]

    count = ensure_course_loaded("course-b", settings=settings)
    results = search("database", top_k=5, course_ids=["course-b"])
    stale_results = search("automation", top_k=5, course_ids=["course-a"])

    assert count == 1
    assert [chunk.chunk_id for chunk, _ in results] == ["b1"]
    assert stale_results == []


def test_ensure_course_loaded_switches_same_course_across_persist_roots(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, ensure_course_loaded, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    settings_a = Settings()
    settings_a.vector_store.persist_dir = str(root_a)
    settings_b = Settings()
    settings_b.vector_store.persist_dir = str(root_b)

    course_a_root_a = [Chunk(chunk_id="a-root", doc_id="doc-a", course_id="course-a", text="automation testing")]
    course_a_root_b = [Chunk(chunk_id="b-root", doc_id="doc-b", course_id="course-a", text="database indexing")]

    build_index_for_course("course-a", course_a_root_a, settings=settings_a)
    build_index_for_course("course-a", course_a_root_b, settings=settings_b)
    build_index_for_course("course-a", course_a_root_a, settings=settings_a)

    active_root_a_results = search("automation", top_k=5, course_ids=["course-a"])
    assert [chunk.chunk_id for chunk, _ in active_root_a_results] == ["a-root"]

    count = ensure_course_loaded("course-a", settings=settings_b)
    switched_results = search("database", top_k=5, course_ids=["course-a"])
    stale_results = search("automation", top_k=5, course_ids=["course-a"])

    assert count == 1
    assert [chunk.chunk_id for chunk, _ in switched_results] == ["b-root"]
    assert stale_results == []


def test_default_course_builds_and_loads_through_scoped_helpers(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, course_index_path, ensure_course_loaded, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    default_course = "默认课程"
    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    default_chunks = [
        Chunk(chunk_id="d1", doc_id="doc-d", course_id=default_course, text="default course note"),
    ]

    count = build_index_for_course("", default_chunks, settings=settings)
    assert count == 1
    assert course_index_path("", settings).exists()

    build_index_for_course(
        "course-b",
        [Chunk(chunk_id="b1", doc_id="doc-b", course_id="course-b", text="branching strategy")],
        settings=settings,
    )

    loaded = ensure_course_loaded("", settings=settings)
    results = search("default", top_k=5, course_ids=[default_course])

    assert loaded == 1
    assert [chunk.chunk_id for chunk, _ in results] == ["d1"]


def test_search_single_document_scope_returns_overlap_match(tmp_path):
    from final_agent.knowledge.bm25_index import build_index_for_course, search
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    build_index_for_course(
        "course-single",
        [Chunk(chunk_id="s1", doc_id="doc-s", course_id="course-single", text="database indexing")],
        settings=settings,
    )

    results = search("database", top_k=5, course_ids=["course-single"])

    assert [chunk.chunk_id for chunk, _ in results] == ["s1"]
