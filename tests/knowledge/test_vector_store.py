from __future__ import annotations

import numpy as np


class FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self.added: dict = {}
        self.queries: list[dict] = []
        self.deleted_ids: list[str] = []
        self.return_numpy_embeddings = False

    def add(self, **kwargs):
        self.added = kwargs

    def query(self, **kwargs):
        self.queries.append(kwargs)
        if self.name.endswith("course-a_01cd93726e"):
            return {
                "ids": [["a1"]],
                "documents": [["automation testing"]],
                "metadatas": [[{"doc_id": "doc-a", "course_id": "course-a", "heading_path": "", "char_start": 0, "char_end": 18, "page_num": 1}]],
                "distances": [[0.2]],
            }
        if self.name.endswith("course-b_e98ca17f32"):
            return {
                "ids": [["b1"]],
                "documents": [["database indexing"]],
                "metadatas": [[{"doc_id": "doc-b", "course_id": "course-b", "heading_path": "", "char_start": 0, "char_end": 17, "page_num": 1}]],
                "distances": [[0.1]],
            }
        if self.name == "kb" and kwargs.get("where") == {"doc_id": {"$in": ["doc-legacy"]}}:
            return {
                "ids": [["legacy-1"]],
                "documents": [["legacy automation"]],
                "metadatas": [[{"doc_id": "doc-legacy", "course_id": "course-legacy", "heading_path": "", "char_start": 0, "char_end": 17, "page_num": 1}]],
                "distances": [[0.05]],
            }
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get(self, **kwargs):
        if self.name == "kb" and kwargs.get("where") == {"doc_id": {"$in": ["doc-legacy"]}}:
            payload = {
                "ids": ["legacy-1"],
                "documents": ["legacy automation"],
                "metadatas": [{"doc_id": "doc-legacy", "course_id": "course-legacy", "heading_path": "", "char_start": 0, "char_end": 17, "page_num": 1}],
            }
            if "embeddings" in kwargs.get("include", []):
                payload["embeddings"] = np.array([[0.1, 0.2]]) if self.return_numpy_embeddings else [[0.1, 0.2]]
            return payload
        return {"ids": []}

    def count(self):
        return len(self.added.get("ids", []))

    def delete(self, *, ids):
        self.deleted_ids.extend(ids)


class FakeClient:
    def __init__(self):
        self.collections: dict[str, FakeCollection] = {}

    def get_or_create_collection(self, *, name: str, metadata: dict):
        self.collections.setdefault(name, FakeCollection(name))
        return self.collections[name]


def test_course_collection_name_is_sanitized_and_stable():
    from final_agent.knowledge.vector_store import course_collection_name
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "final-agent"

    assert course_collection_name("course/a", settings=settings).startswith("final-agent_course_course-a_")
    assert course_collection_name(r"course\a", settings=settings).startswith("final-agent_course_course-a_")
    assert course_collection_name("course/a", settings=settings) != course_collection_name(r"course\a", settings=settings)
    assert course_collection_name("", settings=settings) == "final-agent_course_default_0d18ee3856"


def test_add_chunks_writes_to_the_chunk_course_collection(monkeypatch):
    from final_agent.knowledge import vector_store
    from final_agent.schemas import Chunk
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "kb"
    fake_client = FakeClient()
    monkeypatch.setattr(vector_store, "_get_client", lambda settings: fake_client)

    count = vector_store.add_chunks(
        [(Chunk(chunk_id="a1", doc_id="doc-a", course_id="course-a", text="automation"), np.array([0.1, 0.2]))],
        settings=settings,
    )

    assert count == 1
    assert list(fake_client.collections) == ["kb_course_course-a_01cd93726e"]
    assert fake_client.collections["kb_course_course-a_01cd93726e"].added["ids"] == ["a1"]


def test_query_without_scope_queries_each_registered_course_collection(monkeypatch):
    from final_agent.knowledge import vector_store
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "kb"
    fake_client = FakeClient()
    monkeypatch.setattr(vector_store, "_get_client", lambda settings: fake_client)
    monkeypatch.setattr(
        vector_store,
        "_list_registered_course_ids",
        lambda settings: ["course-a", "course-b"],
    )

    results = vector_store.query(np.array([0.1, 0.2]), top_k=5, settings=settings, course_ids=None)

    assert [chunk.chunk_id for chunk, _ in results] == ["b1", "a1"]
    assert set(fake_client.collections) == {
        "kb_course_course-a_01cd93726e",
        "kb_course_course-b_e98ca17f32",
    }


def test_query_falls_back_to_legacy_collection_for_existing_global_data(monkeypatch):
    from final_agent.knowledge import vector_store
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "kb"
    fake_client = FakeClient()
    monkeypatch.setattr(vector_store, "_get_client", lambda settings: fake_client)
    monkeypatch.setattr(vector_store, "_doc_ids_for_course", lambda course_id, settings: ["doc-legacy"])

    results = vector_store.query(np.array([0.1, 0.2]), top_k=5, settings=settings, course_ids=["course-legacy"])

    assert [chunk.chunk_id for chunk, _ in results] == ["legacy-1"]
    assert set(fake_client.collections) == {
        "kb_course_course-legacy_5d832e4543",
        "kb",
    }


def test_get_chunks_by_course_merges_legacy_global_collection(monkeypatch):
    from final_agent.knowledge import vector_store
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "kb"
    fake_client = FakeClient()
    monkeypatch.setattr(vector_store, "_get_client", lambda settings: fake_client)
    monkeypatch.setattr(vector_store, "_doc_ids_for_course", lambda course_id, settings: ["doc-legacy"])

    chunks = vector_store.get_chunks_by_course("course-legacy", settings=settings)

    assert [chunk.chunk_id for chunk in chunks] == ["legacy-1"]
    assert chunks[0].course_id == "course-legacy"


def test_migrate_legacy_course_collection_copies_embeddings_without_deleting_legacy(monkeypatch):
    from final_agent.knowledge import vector_store
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "kb"
    fake_client = FakeClient()
    monkeypatch.setattr(vector_store, "_get_client", lambda settings: fake_client)
    monkeypatch.setattr(vector_store, "_doc_ids_for_course", lambda course_id, settings: ["doc-legacy"])

    summary = vector_store.migrate_legacy_course_collection("course-legacy", settings=settings)

    target = fake_client.collections["kb_course_course-legacy_5d832e4543"]
    legacy = fake_client.collections["kb"]
    assert summary == {
        "course_id": "course-legacy",
        "legacy_chunks": 1,
        "migrated_chunks": 1,
        "skipped_existing": 0,
    }
    assert target.added["ids"] == ["legacy-1"]
    assert target.added["embeddings"] == [[0.1, 0.2]]
    assert legacy.deleted_ids == []


def test_migrate_legacy_course_collection_accepts_numpy_embeddings(monkeypatch):
    from final_agent.knowledge import vector_store
    from final_agent.settings import Settings

    settings = Settings()
    settings.vector_store.collection_name = "kb"
    fake_client = FakeClient()
    legacy = fake_client.get_or_create_collection(name="kb", metadata={})
    legacy.return_numpy_embeddings = True
    monkeypatch.setattr(vector_store, "_get_client", lambda settings: fake_client)
    monkeypatch.setattr(vector_store, "_doc_ids_for_course", lambda course_id, settings: ["doc-legacy"])

    summary = vector_store.migrate_legacy_course_collection("course-legacy", settings=settings)

    assert summary["migrated_chunks"] == 1
    assert fake_client.collections["kb_course_course-legacy_5d832e4543"].added["embeddings"] == [[0.1, 0.2]]
