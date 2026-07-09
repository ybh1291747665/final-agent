from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def reset_metadata_cache():
    from final_agent.knowledge import metadata

    metadata._METADATA_CACHE = None
    metadata._METADATA_CACHE_PATH = None
    yield
    metadata._METADATA_CACHE = None
    metadata._METADATA_CACHE_PATH = None


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


def test_register_document_tracks_content_signature(tmp_path):
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
        content_signature="sha256:abc",
    )

    persisted = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert persisted["documents"]["doc-a"]["content_signature"] == "sha256:abc"


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
    assert info["course-a"]["bm25_snapshot_path"] == "bm25_course-a.json"


def test_create_course_lists_empty_courses_before_documents_exist(tmp_path):
    from final_agent.knowledge import metadata
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)

    created = metadata.create_course("软件工程", settings=settings)

    assert created is True
    assert metadata.create_course("软件工程", settings=settings) is False
    assert metadata.list_courses(settings) == ["软件工程"]

    info = metadata.list_course_index_info(settings)
    assert info["软件工程"] == {
        "chunk_count": 0,
        "doc_ids": [],
        "bm25_snapshot_path": "",
    }


def test_delete_empty_course_removes_explicit_course(tmp_path):
    from final_agent.knowledge import metadata
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    metadata.create_course("误输课程", settings=settings)

    assert metadata.delete_empty_course("误输课程", settings=settings) is True
    assert metadata.list_courses(settings) == []
    assert "误输课程" not in metadata.list_course_index_info(settings)


def test_delete_empty_course_rejects_course_with_documents(tmp_path):
    from final_agent.knowledge import metadata
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path)
    metadata.create_course("软件工程", settings=settings)
    metadata.register_document("doc-a", "a.md", 1, settings=settings, course_id="软件工程")

    assert metadata.delete_empty_course("软件工程", settings=settings) is False
    assert metadata.list_courses(settings) == ["软件工程"]
    assert metadata.list_course_index_info(settings)["软件工程"]["doc_ids"] == ["doc-a"]


def test_metadata_cache_is_scoped_by_persist_dir(tmp_path):
    from final_agent.knowledge import metadata
    from final_agent.settings import Settings

    settings_a = Settings()
    settings_a.vector_store.persist_dir = str(tmp_path / "a")
    settings_b = Settings()
    settings_b.vector_store.persist_dir = str(tmp_path / "b")

    metadata.register_document("doc-a", "a.md", 1, settings=settings_a, course_id="course-a")

    assert metadata.list_documents(settings_b) == {}
    assert metadata.list_course_index_info(settings_b) == {}
