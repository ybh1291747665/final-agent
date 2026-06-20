from __future__ import annotations

from pydantic import BaseModel, Field

from final_agent.agent.models import AgentStatus, GradeResult, QuizQuestion, StudyPlanStep, ToolTraceEntry


class CreateSessionRequest(BaseModel):
    learning_goal: str = Field(min_length=3, max_length=500)
    course_ids: list[str] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class SessionResponse(BaseModel):
    session_id: str
    status: AgentStatus
    plan: list[StudyPlanStep]
    quiz: QuizQuestion | None = None
    grade: GradeResult | None = None
    next_action: str = ""


class MasteryResponse(BaseModel):
    mastery: dict


class TraceResponse(BaseModel):
    trace: list[ToolTraceEntry]
