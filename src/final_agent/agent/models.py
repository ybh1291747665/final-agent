from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from final_agent.agent.roles import AgentRole
from final_agent.schemas import ReadingContext


AgentStatus = Literal["planning", "running", "waiting_for_answer", "completed", "failed"]


class StudyPlanStep(BaseModel):
    step_id: str
    objective: str
    tool_name: str
    completed: bool = False


class QuizQuestion(BaseModel):
    question_id: str
    topic: str
    prompt: str
    expected_points: list[str]
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class GradeResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    covered_points: list[str] = Field(default_factory=list)
    missed_points: list[str] = Field(default_factory=list)
    feedback: str


class MasteryRecord(BaseModel):
    topic: str
    score: float = Field(ge=0.0, le=1.0)
    attempts: int = 0


class ToolTraceEntry(BaseModel):
    tool_name: str
    input_summary: str
    ok: bool
    elapsed_ms: int
    error: str = ""
    sequence_no: int = 0


class ToolResult(BaseModel):
    ok: bool
    value: Any = None
    error: str = ""
    elapsed_ms: int = 0


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentToolTraceEntry(BaseModel):
    agent_role: AgentRole
    tool_name: str = ""
    input_summary: str = ""
    output_summary: str = ""
    ok: bool = True
    elapsed_ms: int = 0
    error: str = ""
    fallback_reason: str = ""
    sequence_no: int = 0


class CriticWarning(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning"] = "warning"


class EvidenceSnapshot(BaseModel):
    chunk_id: str
    doc_id: str = ""
    source_path: str = ""
    page_num: int | None = None
    heading: str = ""
    summary: str = ""
    score: float = 0.0
    retrieval_source: str = ""


class ContextBudget(BaseModel):
    max_evidence_items: int = Field(default=3, ge=1, le=10)
    max_summary_chars: int = Field(default=220, ge=80, le=1000)
    max_material_chars: int = Field(default=1200, ge=200, le=6000)
    max_evidence_tokens: int = Field(default=240, ge=40, le=4000)
    max_material_tokens: int = Field(default=900, ge=100, le=8000)
    max_history_tokens: int = Field(default=2000, ge=200, le=32000)


class EvidencePacket(BaseModel):
    query: str
    course_ids: list[str] = Field(default_factory=list)
    reading_context: ReadingContext | None = None
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    evidence_snapshots: list[EvidenceSnapshot] = Field(default_factory=list)
    query_fingerprint: str = ""
    created_turn: int = 0
    budget: ContextBudget = Field(default_factory=ContextBudget)


class AnswerQualityReport(BaseModel):
    citation_count: int = 0
    missing_citation_count: int = 0
    unsupported_citation_count: int = 0
    evidence_count: int = 0
    needs_revision: bool = False
    warnings: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    session_id: str
    learning_goal: str
    course_ids: list[str] = Field(default_factory=list)
    reading_context: ReadingContext | None = None
    plan: list[StudyPlanStep] = Field(default_factory=list)
    current_step: int = 0
    quiz: QuizQuestion | None = None
    learner_answer: str = ""
    grade: GradeResult | None = None
    tool_trace: list[ToolTraceEntry] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0, le=6)
    status: AgentStatus = "planning"
    next_action: str = ""
    agent_plan: list[str] = Field(default_factory=list)
    agent_trace: list[AgentToolTraceEntry] = Field(default_factory=list)
    critic_warnings: list[CriticWarning] = Field(default_factory=list)
    evidence_snapshots: list[EvidenceSnapshot] = Field(default_factory=list)
    evidence_packet: EvidencePacket | None = None
    quality_report: AnswerQualityReport | None = None
    session_summary: str = ""
    turn_index: int = 0
    retrieval_decision: str = ""
    current_agent_role: str = ""
