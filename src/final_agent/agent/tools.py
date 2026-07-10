from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from final_agent.agent.critics import verify_evidence as critic_verify_evidence
from final_agent.agent.critics import verify_grade_consistency as critic_verify_grade_consistency
from final_agent.agent.critics import verify_answer_quality as critic_verify_answer_quality
from final_agent.agent.models import EvidenceSnapshot
from final_agent.agent.graders import DeterministicGrader
from final_agent.agent.models import ToolResult
from final_agent.agent.quiz_generators import DeterministicQuizGenerator
from final_agent.retrieval import pipeline as retrieval_pipeline
from final_agent.schemas import ReadingContext


class SearchCourseMaterialInput(BaseModel):
    query: str
    course_ids: list[str] = Field(default_factory=list)
    top_k: int = 5
    reading_context: ReadingContext | None = None


class SummarizeCourseInput(BaseModel):
    doc_id: str
    mode: str = "key_points"


class GenerateQuizInput(BaseModel):
    topic: str
    course_ids: list[str] = Field(default_factory=list)
    count: int = 1
    materials: list[Any] = Field(default_factory=list)


class GradeAnswerInput(BaseModel):
    question: str
    expected_points: list[str] = Field(default_factory=list)
    learner_answer: str
    materials: list[Any] = Field(default_factory=list)


class GetLearningProfileInput(BaseModel):
    session_id: str


class UpdateMasteryInput(BaseModel):
    session_id: str
    topic: str
    score: float


class VerifyEvidenceInput(BaseModel):
    quiz_prompt: str = ""
    evidence_count: int = 0


class VerifyGradeConsistencyInput(BaseModel):
    score: float
    next_action: str


class VerifyAnswerQualityInput(BaseModel):
    answer: str = ""
    evidence: list[EvidenceSnapshot] = Field(default_factory=list)


def run_tool(operation: Callable[[], Any]) -> ToolResult:
    started = perf_counter()
    try:
        return ToolResult(ok=True, value=operation(), elapsed_ms=int((perf_counter() - started) * 1000))
    except (RuntimeError, ValueError, TimeoutError) as exc:
        return ToolResult(ok=False, error=str(exc), elapsed_ms=int((perf_counter() - started) * 1000))


def search_course_material(
    query: str,
    course_ids: list[str] | None = None,
    top_k: int = 5,
    reading_context: ReadingContext | None = None,
) -> ToolResult:
    if reading_context is None:
        return run_tool(
            lambda: retrieval_pipeline.search(
                query,
                top_k=top_k,
                course_ids=course_ids or [],
            )
        )
    return run_tool(
        lambda: retrieval_pipeline.search(
            query,
            top_k=top_k,
            course_ids=course_ids or [],
            reading_context=reading_context,
        )
    )


def summarize_course(doc_id: str, mode: str = "key_points") -> ToolResult:
    def _op():
        from final_agent.generation.summarizer import summarize_document

        return summarize_document(doc_id, mode)

    return run_tool(_op)


def generate_quiz(
    topic: str,
    course_ids: list[str] | None = None,
    count: int = 1,
    *,
    quiz_generator=None,
    materials: list[Any] | None = None,
) -> ToolResult:
    generator = quiz_generator or DeterministicQuizGenerator()
    selected_materials = [] if materials is None else materials
    if hasattr(generator, "generate_with_evidence"):
        return run_tool(lambda: generator.generate_with_evidence(topic, course_ids or [], count, materials=selected_materials))
    return run_tool(lambda: generator.generate(topic, course_ids or [], count))


def grade_answer(
    question: str,
    expected_points: list[str],
    learner_answer: str,
    *,
    grader: Any | None = None,
    materials: list[Any] | None = None,
) -> ToolResult:
    selected_grader = DeterministicGrader() if grader is None else grader
    selected_materials = [] if materials is None else materials
    return run_tool(
        lambda: selected_grader.grade(
            question,
            expected_points,
            learner_answer,
            materials=selected_materials,
        )
    )


def get_learning_profile(session_id: str, repository: Any | None = None) -> ToolResult:
    return run_tool(lambda: repository.get_mastery(session_id) if repository else {})


def update_mastery(session_id: str, topic: str, score: float, repository: Any | None = None) -> ToolResult:
    return run_tool(lambda: repository.upsert_mastery(session_id, topic, score) if repository else None)


def verify_evidence(quiz_prompt: str, evidence_count: int) -> ToolResult:
    return run_tool(lambda: critic_verify_evidence(quiz_prompt=quiz_prompt, evidence_count=evidence_count))


def verify_grade_consistency(score: float, next_action: str) -> ToolResult:
    return run_tool(lambda: critic_verify_grade_consistency(score=score, next_action=next_action))


def verify_answer_quality(answer: str, evidence: list[EvidenceSnapshot]) -> ToolResult:
    return run_tool(lambda: critic_verify_answer_quality(answer=answer, evidence=evidence))


TOOL_REGISTRY = {
    "search_course_material": SearchCourseMaterialInput,
    "summarize_course": SummarizeCourseInput,
    "generate_quiz": GenerateQuizInput,
    "grade_answer": GradeAnswerInput,
    "get_learning_profile": GetLearningProfileInput,
    "update_mastery": UpdateMasteryInput,
    "verify_evidence": VerifyEvidenceInput,
    "verify_grade_consistency": VerifyGradeConsistencyInput,
    "verify_answer_quality": VerifyAnswerQualityInput,
}
