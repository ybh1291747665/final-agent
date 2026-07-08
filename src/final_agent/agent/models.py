from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from final_agent.agent.roles import AgentRole


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


class AgentState(BaseModel):
    session_id: str
    learning_goal: str
    course_ids: list[str] = Field(default_factory=list)
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
    current_agent_role: str = ""
