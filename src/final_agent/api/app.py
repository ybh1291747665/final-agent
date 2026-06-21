from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException

from final_agent.agent.graders import DeterministicGrader, LlmGrader
from final_agent.agent.graph import run_study_turn
from final_agent.agent.models import AgentState
from final_agent.agent.quiz_generators import DeterministicQuizGenerator
from final_agent.api.schemas import CreateSessionRequest, MasteryResponse, SendMessageRequest, SessionResponse, TraceResponse
from final_agent.knowledge import bm25_load, chroma_get_all
from final_agent.memory.repository import MemoryRepository
from final_agent.settings import load_settings


logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, repository: MemoryRepository, quiz_generator=None, grader=None):
        self.repository = repository
        self.quiz_generator = DeterministicQuizGenerator() if quiz_generator is None else quiz_generator
        self.grader = LlmGrader(fallback=DeterministicGrader()) if grader is None else grader

    def _response(self, state: AgentState) -> SessionResponse:
        return SessionResponse(
            session_id=state.session_id,
            status=state.status,
            plan=state.plan,
            quiz=state.quiz,
            grade=state.grade,
            next_action=state.next_action,
        )

    def create_session(self, payload: CreateSessionRequest) -> SessionResponse:
        state = AgentState(session_id=uuid4().hex, learning_goal=payload.learning_goal, course_ids=payload.course_ids)
        state = run_study_turn(
            state,
            repository=self.repository,
            quiz_generator=self.quiz_generator,
            grader=self.grader,
        )
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
        state = run_study_turn(
            state,
            repository=self.repository,
            quiz_generator=self.quiz_generator,
            grader=self.grader,
        )
        self.repository.save_session(state)
        for trace in state.tool_trace[before:]:
            self.repository.append_trace(state.session_id, trace)
        return self._response(state)

    def get_session(self, session_id: str) -> SessionResponse:
        try:
            return self._response(self.repository.get_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc


def _warm_knowledge_cache() -> None:
    try:
        settings = load_settings()
        chunks = chroma_get_all(settings=settings)
        bm25_load(chunks, settings=settings)
    except Exception as exc:
        logger.warning("Study Coach API knowledge warmup skipped: %s", exc)


def create_app(repository: MemoryRepository | None = None, quiz_generator=None, grader=None) -> FastAPI:
    app = FastAPI(title="final-agent Study Coach API")
    repo = MemoryRepository() if repository is None else repository
    service = AgentService(repo, quiz_generator=quiz_generator, grader=grader)
    _warm_knowledge_cache()

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
