from __future__ import annotations

import httpx
import pytest


def test_agent_client_creates_session_with_http_transport():
    from final_agent.ui.agent_client import AgentApiClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sessions"
        return httpx.Response(201, json={"session_id": "s1", "status": "waiting_for_answer", "plan": [], "quiz": None, "grade": None})

    client = AgentApiClient(base_url="http://test", http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test"))

    response = client.create_session("review CI", ["course-a"])

    assert response["session_id"] == "s1"


def test_agent_client_raises_readable_error_on_non_2xx():
    from final_agent.ui.agent_client import AgentApiClient, AgentApiError

    client = AgentApiClient(base_url="http://test", http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503, json={"detail": "temporary"})), base_url="http://test"))

    with pytest.raises(AgentApiError, match="temporary"):
        client.get_session("s1")


def test_agent_client_reads_base_url_from_environment(monkeypatch):
    from final_agent.ui.agent_client import AgentApiClient

    monkeypatch.setenv("FINAL_AGENT_API_BASE_URL", "http://127.0.0.1:9001/")

    client = AgentApiClient(http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))))

    assert client.base_url == "http://127.0.0.1:9001"


def test_agent_api_client_sends_reading_context():
    from final_agent.ui.agent_client import AgentApiClient

    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"session_id": "s1"})

    client = AgentApiClient(
        http_client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="http://test",
        )
    )

    client.create_session(
        "review CI",
        ["course-a"],
        reading_context={"doc_id": "doc-a", "page_num": 12, "page_boost_enabled": True},
    )

    assert requests[0].read().decode() == (
        '{"learning_goal":"review CI","course_ids":["course-a"],'
        '"reading_context":{"doc_id":"doc-a","page_num":12,"page_boost_enabled":true}}'
    )


def test_agent_api_client_reads_document_info_and_page():
    from final_agent.ui.agent_client import AgentApiClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/documents/doc-a":
            return httpx.Response(200, json={"doc_id": "doc-a", "total_pages": 2})
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})

    client = AgentApiClient(
        http_client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="http://test",
        )
    )

    assert client.get_document("doc-a")["total_pages"] == 2
    assert client.get_document_page("doc-a", 2, 125) == b"\x89PNG"
