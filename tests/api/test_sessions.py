from __future__ import annotations


def test_session_api_contract(tmp_path):
    from fastapi.testclient import TestClient
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    client = TestClient(app)

    created = client.post("/sessions", json={"learning_goal": "review CI", "course_ids": ["course-a"]})
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    assert created.json()["status"] == "waiting_for_answer"

    answered = client.post(f"/sessions/{session_id}/messages", json={"message": "automation"})
    assert answered.status_code == 200
    assert answered.json()["status"] == "completed"

    assert client.get(f"/sessions/{session_id}").status_code == 200
    assert client.get(f"/sessions/{session_id}/mastery").status_code == 200
    assert client.get(f"/sessions/{session_id}/trace").status_code == 200
    assert client.get("/sessions/missing").status_code == 404


def test_session_api_returns_conflict_for_answer_before_question(tmp_path):
    from fastapi.testclient import TestClient
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    client = TestClient(app)

    response = client.post("/sessions/missing/messages", json={"message": "hello"})

    assert response.status_code == 404
