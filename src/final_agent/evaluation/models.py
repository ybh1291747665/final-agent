from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EvaluationCategory = Literal["retrieval", "tool_selection", "adaptive_review"]


class EvaluationCase(BaseModel):
    case_id: str
    category: EvaluationCategory
    course_ids: list[str] = Field(default_factory=list)
    user_input: str
    expected_tools: list[str] = Field(default_factory=list)
    required_citations: list[str] = Field(default_factory=list)
    expected_outcome: str
    expected_score_band: Literal["low", "medium", "high"] | None = None


class EvaluationResult(BaseModel):
    case_id: str
    completed: bool = False
    expected_tools: list[str] = Field(default_factory=list)
    actual_tools: list[str] = Field(default_factory=list)
    required_citations: list[str] = Field(default_factory=list)
    retrieved_citations: list[str] = Field(default_factory=list)
    actual_citations: list[str] = Field(default_factory=list)
    citation_diagnostics: dict[str, object] = Field(default_factory=dict)
    semantic_relevance_score: float | None = None
    semantic_relevance_reason: str = ""
    expected_score_band: Literal["low", "medium", "high"] | None = None
    actual_score: float | None = None
    elapsed_ms: int = 0
    error: str = ""


class EvaluationSummary(BaseModel):
    total_cases: int = 0
    task_completion_rate: float = 0.0
    tool_selection_accuracy: float = 0.0
    citation_grounding_rate: float = 0.0
    retrieval_recall_at_5: float = 0.0
    evidence_recall_at_3: float = 0.0
    citation_precision: float = 0.0
    grading_agreement: float = 0.0
    mean_latency_ms: int = 0
    p95_latency_ms: int = 0
    error_rate: float = 0.0
