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
