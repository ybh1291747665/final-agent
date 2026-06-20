from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException

from final_agent.agent.graph import run_study_turn
from final_agent.agent.models import AgentState
from final_agent.api.schemas import CreateSessionRequest, MasteryResponse, SendMessageRequest, SessionResponse, TraceResponse
from final_agent.memory.repository import MemoryRepository


class AgentService:
    def __init__(self, repository: MemoryRepository):
        self.repository = repository

    def _response(self, state: AgentState) -> SessionResponse:
        return SessionResponse(session_id=state.session_id, status=state.status, plan=state.plan, quiz=state.quiz, grade=state.grade)

    def create_session(self, payload: CreateSessionRequest) -> SessionResponse:
        state = AgentState(session_id=uuid4().hex, learning_goal=payload.learning_goal, course_ids=payload.course_ids)
        state = run_study_turn(state, repository=self.repository)
        self.repository.create_session(state)
        for trace in state.tool_trace:
            self.repository.append_trace(state.session_id, trace)
        return self._response(state)

    def send_message(self, session_id: str, message: str) -> SessionResponse:
        try:
            state = self.repository.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc
        if state.status != "waiting_for_answer":
            raise HTTPException(status_code=409, detail="Session is not waiting for an answer")
        state.learner_answer = message
        before = len(state.tool_trace)
        state = run_study_turn(state, repository=self.repository)
        self.repository.save_session(state)
        for trace in state.tool_trace[before:]:
            self.repository.append_trace(state.session_id, trace)
        return self._response(state)

    def get_session(self, session_id: str) -> SessionResponse:
        try:
            return self._response(self.repository.get_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc


def create_app(repository: MemoryRepository | None = None) -> FastAPI:
    app = FastAPI(title="final-agent Study Coach API")
    repo = repository or MemoryRepository()
    service = AgentService(repo)

    def get_service() -> AgentService:
        return service

    @app.post("/sessions", response_model=SessionResponse, status_code=201)
    def create_session(payload: CreateSessionRequest, service: AgentService = Depends(get_service)):
        return service.create_session(payload)

    @app.post("/sessions/{session_id}/messages", response_model=SessionResponse)
    def send_message(session_id: str, payload: SendMessageRequest, service: AgentService = Depends(get_service)):
        return service.send_message(session_id, payload.message)

    @app.get("/sessions/{session_id}", response_model=SessionResponse)
    def get_session(session_id: str, service: AgentService = Depends(get_service)):
        return service.get_session(session_id)

    @app.get("/sessions/{session_id}/mastery", response_model=MasteryResponse)
    def get_mastery(session_id: str):
        try:
            repo.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc
        return MasteryResponse(mastery={topic: record.model_dump() for topic, record in repo.get_mastery(session_id).items()})

    @app.get("/sessions/{session_id}/trace", response_model=TraceResponse)
    def get_trace(session_id: str):
        try:
            repo.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc
        return TraceResponse(trace=repo.list_trace(session_id))

    return app


app = create_app()
