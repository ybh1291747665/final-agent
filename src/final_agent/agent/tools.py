from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from final_agent.agent.models import GradeResult, ToolResult
from final_agent.agent.quiz_generators import DeterministicQuizGenerator
from final_agent.retrieval import pipeline as retrieval_pipeline


class SearchCourseMaterialInput(BaseModel):
    query: str
    course_ids: list[str] = Field(default_factory=list)
    top_k: int = 5


class SummarizeCourseInput(BaseModel):
    doc_id: str
    mode: str = "key_points"


class GenerateQuizInput(BaseModel):
    topic: str
    course_ids: list[str] = Field(default_factory=list)
    count: int = 1


def run_tool(operation: Callable[[], Any]) -> ToolResult:
    started = perf_counter()
    try:
        return ToolResult(ok=True, value=operation(), elapsed_ms=int((perf_counter() - started) * 1000))
    except (RuntimeError, ValueError, TimeoutError) as exc:
        return ToolResult(ok=False, error=str(exc), elapsed_ms=int((perf_counter() - started) * 1000))


def search_course_material(query: str, course_ids: list[str] | None = None, top_k: int = 5) -> ToolResult:
    return run_tool(lambda: retrieval_pipeline.search(query, top_k=top_k, course_ids=course_ids or []))


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
) -> ToolResult:
    generator = quiz_generator or DeterministicQuizGenerator()
    return run_tool(lambda: generator.generate(topic, course_ids or [], count))


def grade_answer(question: str, expected_points: list[str], learner_answer: str) -> ToolResult:
    def _op() -> GradeResult:
        normalized = learner_answer.lower()
        covered = [point for point in expected_points if point.lower() in normalized]
        missed = [point for point in expected_points if point not in covered]
        score = len(covered) / len(expected_points) if expected_points else 0.0
        return GradeResult(
            score=score,
            covered_points=covered,
            missed_points=missed,
            feedback="Covered all expected points." if not missed else f"Review: {', '.join(missed)}",
        )

    return run_tool(_op)


def get_learning_profile(session_id: str, repository: Any | None = None) -> ToolResult:
    return run_tool(lambda: repository.get_mastery(session_id) if repository else {})


def update_mastery(session_id: str, topic: str, score: float, repository: Any | None = None) -> ToolResult:
    return run_tool(lambda: repository.upsert_mastery(session_id, topic, score) if repository else None)


TOOL_REGISTRY = {
    "search_course_material": SearchCourseMaterialInput,
    "summarize_course": SummarizeCourseInput,
    "generate_quiz": GenerateQuizInput,
    "grade_answer": None,
    "get_learning_profile": None,
    "update_mastery": None,
}
