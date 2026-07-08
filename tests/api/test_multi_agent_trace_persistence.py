from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_api_persists_agent_trace_rows(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "api.sqlite")
    app = create_app(repository=repo)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/sessions", json={"learning_goal": "review CI", "course_ids": []})
        session_id = created.json()["session_id"]

    trace = repo.list_agent_trace(session_id)

    assert [entry.agent_role.value for entry in trace] == ["supervisor", "retrieval", "quiz"]
