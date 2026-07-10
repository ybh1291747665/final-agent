from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response

from final_agent.agent.graders import DeterministicGrader, LlmGrader
from final_agent.agent.models import AgentState
from final_agent.agent.orchestrator import MultiAgentOrchestrator
from final_agent.agent.quiz_generators import select_quiz_generator
from final_agent.api.documents import (
    DocumentNotFoundError,
    DocumentService,
    PageOutOfRangeError,
    UnsupportedDocumentError,
)
from final_agent.api.schemas import (
    CreateSessionRequest,
    DocumentInfoResponse,
    MasteryResponse,
    SendMessageRequest,
    SessionResponse,
    TraceResponse,
)
from final_agent.memory.repository import MemoryRepository
from final_agent.settings import load_settings


logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, repository: MemoryRepository, quiz_generator=None, grader=None, orchestrator=None):
        self.repository = repository
        self.quiz_generator = select_quiz_generator(load_settings()) if quiz_generator is None else quiz_generator
        self.grader = LlmGrader(fallback=DeterministicGrader()) if grader is None else grader
        self.orchestrator = orchestrator or MultiAgentOrchestrator(
            repository=repository,
            quiz_generator=self.quiz_generator,
            grader=self.grader,
        )

    def _response(self, state: AgentState) -> SessionResponse:
        return SessionResponse(
            session_id=state.session_id,
            status=state.status,
            plan=state.plan,
            quiz=state.quiz,
            grade=state.grade,
            next_action=state.next_action,
            agent_plan=state.agent_plan,
            agent_trace=state.agent_trace,
            critic_warnings=state.critic_warnings,
            evidence_snapshots=state.evidence_snapshots,
            quality_report=state.quality_report,
            session_summary=state.session_summary,
            retrieval_decision=state.retrieval_decision,
        )

    def create_session(self, payload: CreateSessionRequest) -> SessionResponse:
        state = AgentState(
            session_id=uuid4().hex,
            learning_goal=payload.learning_goal,
            course_ids=payload.course_ids,
            reading_context=payload.reading_context,
        )
        state = self.orchestrator.run_turn(state)
        self.repository.create_session(state)
        for trace in state.tool_trace:
            self.repository.append_trace(state.session_id, trace)
        for trace in state.agent_trace:
            self.repository.append_agent_trace(state.session_id, trace)
        return self._response(state)

    def send_message(self, session_id: str, message: str, reading_context=None) -> SessionResponse:
        try:
            state = self.repository.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc
        if state.status != "waiting_for_answer":
            raise HTTPException(status_code=409, detail="Session is not waiting for an answer")
        state.learner_answer = message
        if reading_context is not None:
            state.reading_context = reading_context
        before = len(state.tool_trace)
        before_agent_trace = len(state.agent_trace)
        state = self.orchestrator.run_turn(state)
        self.repository.save_session(state)
        for trace in state.tool_trace[before:]:
            self.repository.append_trace(state.session_id, trace)
        for trace in state.agent_trace[before_agent_trace:]:
            self.repository.append_agent_trace(state.session_id, trace)
        return self._response(state)

    def get_session(self, session_id: str) -> SessionResponse:
        try:
            return self._response(self.repository.get_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown session") from exc

def create_app(
    repository: MemoryRepository | None = None,
    quiz_generator=None,
    grader=None,
    orchestrator=None,
    document_service: DocumentService | None = None,
) -> FastAPI:
    app = FastAPI(title="final-agent Study Coach API")
    repo = MemoryRepository() if repository is None else repository
    service = AgentService(repo, quiz_generator=quiz_generator, grader=grader, orchestrator=orchestrator)
    documents = document_service or DocumentService()

    def get_service() -> AgentService:
        return service

    @app.post("/sessions", response_model=SessionResponse, status_code=201)
    def create_session(payload: CreateSessionRequest, service: AgentService = Depends(get_service)):
        return service.create_session(payload)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "study-coach-api",
            "storage": "sqlite",
        }

    @app.get("/documents/{doc_id}", response_model=DocumentInfoResponse)
    def get_document(doc_id: str):
        try:
            return documents.info(doc_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Document not found") from exc
        except UnsupportedDocumentError as exc:
            raise HTTPException(status_code=415, detail="Document is not a readable PDF") from exc

    @app.get("/documents/{doc_id}/pages/{page_num}")
    def get_document_page(doc_id: str, page_num: int, zoom: int = 100):
        try:
            content = documents.page(doc_id, page_num, zoom)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Document not found") from exc
        except UnsupportedDocumentError as exc:
            raise HTTPException(status_code=415, detail="Document is not a readable PDF") from exc
        except PageOutOfRangeError as exc:
            raise HTTPException(status_code=416, detail="Page out of range") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(content=content, media_type="image/png")

    @app.post("/sessions/{session_id}/messages", response_model=SessionResponse)
    def send_message(session_id: str, payload: SendMessageRequest, service: AgentService = Depends(get_service)):
        return service.send_message(session_id, payload.message, payload.reading_context)

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
