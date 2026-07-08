from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_session_response_exposes_agent_trace_and_warnings(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/sessions", json={"learning_goal": "review CI", "course_ids": []})
        assert created.status_code == 201
        body = created.json()

    assert "agent_plan" in body
    assert "agent_trace" in body
    assert "critic_warnings" in body
    assert [entry["agent_role"] for entry in body["agent_trace"]] == ["supervisor", "retrieval", "quiz"]
