from __future__ import annotations

from pydantic import BaseModel, Field

from final_agent.agent.models import (
    AgentStatus,
    AgentToolTraceEntry,
    AnswerQualityReport,
    CriticWarning,
    EvidenceSnapshot,
    GradeResult,
    QuizQuestion,
    StudyPlanStep,
    ToolTraceEntry,
)
from final_agent.schemas import ReadingContext


class CreateSessionRequest(BaseModel):
    learning_goal: str = Field(min_length=3, max_length=500)
    course_ids: list[str] = Field(default_factory=list)
    reading_context: ReadingContext | None = None


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    reading_context: ReadingContext | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: AgentStatus
    plan: list[StudyPlanStep]
    quiz: QuizQuestion | None = None
    grade: GradeResult | None = None
    next_action: str = ""
    agent_plan: list[str] = Field(default_factory=list)
    agent_trace: list[AgentToolTraceEntry] = Field(default_factory=list)
    critic_warnings: list[CriticWarning] = Field(default_factory=list)
    evidence_snapshots: list[EvidenceSnapshot] = Field(default_factory=list)
    quality_report: AnswerQualityReport | None = None


class MasteryResponse(BaseModel):
    mastery: dict


class TraceResponse(BaseModel):
    trace: list[ToolTraceEntry]


class DocumentInfoResponse(BaseModel):
    doc_id: str
    file_name: str
    media_type: str
    total_pages: int = Field(ge=1)
