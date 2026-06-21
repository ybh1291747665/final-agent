from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from final_agent.agent.models import GradeResult


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
