from __future__ import annotations

import os
from typing import Any

import httpx


class AgentApiError(RuntimeError):
    pass


class AgentApiClient:
    def __init__(self, base_url: str | None = None, http_client: httpx.Client | None = None):
        resolved_base_url = base_url or os.environ.get("FINAL_AGENT_API_BASE_URL", "http://127.0.0.1:8000")
        self.base_url = resolved_base_url.rstrip("/")
        self.client = http_client or httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(10.0, connect=3.0))

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise AgentApiError(str(exc)) from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise AgentApiError(str(detail))
        return response.json()

    def create_session(self, learning_goal: str, course_ids: list[str] | None = None) -> dict[str, Any]:
        return self._request("POST", "/sessions", json={"learning_goal": learning_goal, "course_ids": course_ids or []})

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        return self._request("POST", f"/sessions/{session_id}/messages", json={"message": message})

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}")

    def get_mastery(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/mastery")

    def get_trace(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/trace")
