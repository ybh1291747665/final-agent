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

    def _request_bytes(self, method: str, path: str, **kwargs) -> bytes:
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise AgentApiError(str(exc)) from exc
        if response.status_code >= 400:
            raise AgentApiError(response.text)
        return response.content

    def create_session(
        self,
        learning_goal: str,
        course_ids: list[str] | None = None,
        reading_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "learning_goal": learning_goal,
            "course_ids": course_ids or [],
        }
        if reading_context is not None:
            payload["reading_context"] = reading_context
        return self._request("POST", "/sessions", json=payload)

    def send_message(
        self,
        session_id: str,
        message: str,
        reading_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": message}
        if reading_context is not None:
            payload["reading_context"] = reading_context
        return self._request("POST", f"/sessions/{session_id}/messages", json=payload)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}")

    def get_mastery(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/mastery")

    def get_trace(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/trace")

    def get_document(self, doc_id: str) -> dict[str, Any]:
        return self._request("GET", f"/documents/{doc_id}")

    def get_document_page(self, doc_id: str, page_num: int, zoom: int = 100) -> bytes:
        return self._request_bytes(
            "GET",
            f"/documents/{doc_id}/pages/{page_num}",
            params={"zoom": zoom},
        )
