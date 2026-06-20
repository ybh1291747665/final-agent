from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_session_api_contract(tmp_path, monkeypatch):
    from final_agent.api.app import create_app
    from final_agent.agent.models import ToolResult
    from final_agent.memory.repository import MemoryRepository
    import final_agent.agent.graph as graph_module
    import final_agent.api.app as api_app_module

    monkeypatch.setattr(
        graph_module,
        "search_course_material",
        lambda query, course_ids, top_k: ToolResult(ok=True, value=[], elapsed_ms=1),
    )
    monkeypatch.setattr(api_app_module, "_warm_knowledge_cache", lambda: None)

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post(
            "/sessions",
            json={
                "learning_goal": "review configuration management and version control",
                "course_ids": ["course-a"],
            },
        )
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert created.json()["status"] == "waiting_for_answer"
        assert created.json()["next_action"] == ""

        answered = await client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Configuration management controls revisions, but I still need help with branching."},
        )
        assert answered.status_code == 200
        assert answered.json()["status"] == "completed"
        assert answered.json()["next_action"] == "practice_variant"

        assert (await client.get(f"/sessions/{session_id}")).status_code == 200
        assert (await client.get(f"/sessions/{session_id}/mastery")).status_code == 200
        assert (await client.get(f"/sessions/{session_id}/trace")).status_code == 200
        assert (await client.get("/sessions/missing")).status_code == 404


@pytest.mark.anyio
async def test_session_api_returns_conflict_for_answer_before_question(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository
    import final_agent.api.app as api_app_module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(api_app_module, "_warm_knowledge_cache", lambda: None)

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/sessions/missing/messages", json={"message": "hello"})

        assert response.status_code == 404
    monkeypatch.undo()


def test_create_app_preloads_knowledge(tmp_path, monkeypatch):
    from final_agent.api import app as api_app_module
    from final_agent.memory.repository import MemoryRepository

    calls: dict[str, object] = {}

    def fake_get_all(*, settings=None):
        calls["get_all_settings"] = settings
        return ["chunk-a", "chunk-b"]

    def fake_bm25_load(chunks, *, settings=None):
        calls["chunks"] = list(chunks)
        calls["load_settings"] = settings
        return len(chunks)

    monkeypatch.setattr(api_app_module, "chroma_get_all", fake_get_all, raising=False)
    monkeypatch.setattr(api_app_module, "bm25_load", fake_bm25_load, raising=False)

    api_app_module.create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))

    assert calls["chunks"] == ["chunk-a", "chunk-b"]
    assert calls["get_all_settings"] is not None
    assert calls["load_settings"] is not None
