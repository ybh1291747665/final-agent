from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_session_response_exposes_evidence_snapshots(tmp_path):
    from final_agent.agent.models import AgentState, EvidenceSnapshot, QuizQuestion
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    class FakeOrchestrator:
        def run_turn(self, state: AgentState) -> AgentState:
            state.status = "waiting_for_answer"
            state.quiz = QuizQuestion(
                question_id="q1",
                topic=state.learning_goal,
                prompt="Explain CI.",
                expected_points=["automation"],
            )
            state.evidence_snapshots = [
                EvidenceSnapshot(
                    chunk_id="aaaabbbb1111",
                    doc_id="doc-a",
                    source_path="E:/courses/software-engineering.pdf",
                    page_num=12,
                    heading="CI",
                    summary="CI runs automated tests.",
                    score=0.91,
                    retrieval_source="rrf",
                )
            ]
            return state

    app = create_app(
        repository=MemoryRepository(tmp_path / "api.sqlite"),
        orchestrator=FakeOrchestrator(),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/sessions", json={"learning_goal": "review CI", "course_ids": []})

    assert response.status_code == 201
    body = response.json()
    assert body["evidence_snapshots"] == [
        {
            "chunk_id": "aaaabbbb1111",
            "doc_id": "doc-a",
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 12,
            "heading": "CI",
            "summary": "CI runs automated tests.",
            "score": 0.91,
            "retrieval_source": "rrf",
        }
    ]
