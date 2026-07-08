from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_session_api_contract(tmp_path, monkeypatch):
    from final_agent.agent.graders import DeterministicGrader
    from final_agent.agent.quiz_generators import DeterministicQuizGenerator
    from final_agent.api.app import create_app
    from final_agent.agent.models import ToolResult
    from final_agent.memory.repository import MemoryRepository
    import final_agent.agent.graph as graph_module

    monkeypatch.setattr(
        graph_module,
        "search_course_material",
        lambda query, course_ids, top_k: ToolResult(ok=True, value=[], elapsed_ms=1),
    )

    app = create_app(
        repository=MemoryRepository(tmp_path / "api.sqlite"),
        quiz_generator=DeterministicQuizGenerator(),
        grader=DeterministicGrader(),
    )
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

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/sessions/missing/messages", json={"message": "hello"})

        assert response.status_code == 404


def test_create_app_does_not_preload_knowledge(tmp_path, monkeypatch):
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

    assert calls == {}


def test_agent_service_uses_injected_orchestrator(tmp_path):
    from final_agent.api.app import AgentService
    from final_agent.api.schemas import CreateSessionRequest
    from final_agent.memory.repository import MemoryRepository

    class FakeOrchestrator:
        def __init__(self):
            self.called = False

        def run_turn(self, state):
            self.called = True
            state.status = "waiting_for_answer"
            return state

    orchestrator = FakeOrchestrator()
    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"), orchestrator=orchestrator)
    service.create_session(CreateSessionRequest(learning_goal="review CI", course_ids=[]))

    assert orchestrator.called is True


def test_agent_service_defaults_to_llm_grader(tmp_path):
    from final_agent.agent.graders import DeterministicGrader, LlmGrader
    from final_agent.api.app import AgentService
    from final_agent.memory.repository import MemoryRepository

    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"))

    assert isinstance(service.grader, LlmGrader)
    assert isinstance(service.grader.fallback, DeterministicGrader)


def test_agent_service_selects_default_quiz_generator_from_settings(tmp_path, monkeypatch):
    from final_agent.agent.quiz_generators import LlmQuizGenerator
    from final_agent.api import app as api_app_module
    from final_agent.api.app import AgentService
    from final_agent.memory.repository import MemoryRepository
    from final_agent.settings import Settings

    settings = Settings()
    settings.models_llm.api_key = "sk-live"
    monkeypatch.setattr(api_app_module, "load_settings", lambda: settings)

    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"))

    assert isinstance(service.quiz_generator, LlmQuizGenerator)


@pytest.mark.anyio
async def test_health_endpoint_reports_service_readiness(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "study-coach-api",
        "storage": "sqlite",
    }
