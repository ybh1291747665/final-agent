from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from final_agent.agent.models import GradeResult
from final_agent.generation.llm_client import generate as llm_generate
from final_agent.settings import load_settings


@dataclass
class GradeEvaluationMeta:
    implementation: str
    fallback_reason: str = ""


class DeterministicGrader:
    implementation = "deterministic"

    def grade(
        self,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> GradeResult:
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


class LlmGrader:
    implementation = "llm"

    def __init__(self, fallback: DeterministicGrader | None = None):
        self.fallback = fallback or DeterministicGrader()

    def grade_with_meta(
        self,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> tuple[GradeResult, GradeEvaluationMeta]:
        prompt = (
            "Return only JSON for grading with keys "
            '"score", "covered_points", "missed_points", "feedback". '
            f"Question: {question}\n"
            f"Expected points: {expected_points}\n"
            f"Learner answer: {learner_answer}\n"
            f"Materials: {materials or []}"
        )
        try:
            raw = llm_generate([{"role": "user", "content": prompt}], settings=load_settings())
            data = json.loads(raw)
            grade = GradeResult.model_validate(data)
            return grade, GradeEvaluationMeta(implementation="llm")
        except json.JSONDecodeError as exc:
            grade = self.fallback.grade(question, expected_points, learner_answer, materials=materials)
            return grade, GradeEvaluationMeta(
                implementation="deterministic-fallback",
                fallback_reason=f"JSON decode error: {exc}"[:120],
            )
        except Exception as exc:
            grade = self.fallback.grade(question, expected_points, learner_answer, materials=materials)
            return grade, GradeEvaluationMeta(
                implementation="deterministic-fallback",
                fallback_reason=str(exc)[:120],
            )

    def grade(
        self,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> GradeResult:
        grade, _ = self.grade_with_meta(
            question,
            expected_points,
            learner_answer,
            materials=materials,
        )
        return grade
