from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from final_agent.agent.models import GradeResult
from final_agent.generation.llm_client import generate as llm_generate
from final_agent.settings import Settings
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
        if not missed:
            feedback = "Covered all expected points from the course evidence."
        elif materials:
            evidence_hint = ""
            first = materials[0]
            if isinstance(first, dict):
                heading = str(first.get("heading", "")).strip()
                evidence_hint = f" in {heading}" if heading else ""
            feedback = f"Review course evidence{evidence_hint}: {', '.join(missed)}."
        else:
            feedback = f"Review: {', '.join(missed)}"
        return GradeResult(
            score=score,
            covered_points=covered,
            missed_points=missed,
            feedback=feedback,
        )


class LlmGrader:
    implementation = "llm"

    def __init__(
        self,
        fallback: DeterministicGrader | None = None,
        *,
        llm_callable: Callable[..., str] = llm_generate,
        settings: Settings | None = None,
        settings_loader: Callable[[], Settings] = load_settings,
    ):
        self.fallback = fallback or DeterministicGrader()
        self.llm_callable = llm_callable
        self.settings = settings
        self.settings_loader = settings_loader

    def _fallback(
        self,
        reason: str,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> tuple[GradeResult, GradeEvaluationMeta]:
        grade = self.fallback.grade(question, expected_points, learner_answer, materials=materials)
        return grade, GradeEvaluationMeta(
            implementation="deterministic-fallback",
            fallback_reason=reason[:120],
        )

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
            settings = self.settings if self.settings is not None else self.settings_loader()
            raw = self.llm_callable([{"role": "user", "content": prompt}], settings=settings)
            data = json.loads(raw)
            grade = GradeResult.model_validate(data)
            return grade, GradeEvaluationMeta(implementation="llm")
        except json.JSONDecodeError as exc:
            return self._fallback(
                f"JSON decode error: {exc}",
                question,
                expected_points,
                learner_answer,
                materials=materials,
            )
        except ValidationError as exc:
            return self._fallback(
                f"Validation error: {exc}",
                question,
                expected_points,
                learner_answer,
                materials=materials,
            )
        except Exception as exc:
            return self._fallback(
                str(exc),
                question,
                expected_points,
                learner_answer,
                materials=materials,
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
