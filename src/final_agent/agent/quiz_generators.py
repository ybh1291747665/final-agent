from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from final_agent.agent.models import QuizQuestion
from final_agent.generation.llm_client import generate as llm_generate
from final_agent.settings import load_settings


@dataclass
class QuizGenerationMeta:
    implementation: str
    fallback_reason: str = ""


class DeterministicQuizGenerator:
    implementation = "deterministic"

    def generate(self, topic: str, course_ids: list[str] | None = None, count: int = 1) -> QuizQuestion:
        points = [word for word in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", topic.lower()) if len(word) > 2]
        expected_points = points[:3] or [topic.lower()]
        return QuizQuestion(
            question_id=f"quiz-{abs(hash((topic, count))) % 100000}",
            topic=topic,
            prompt=f"Explain {topic} and mention: {', '.join(expected_points)}.",
            expected_points=expected_points,
        )

    def generate_with_evidence(
        self,
        topic: str,
        course_ids: list[str] | None = None,
        count: int = 1,
        *,
        materials: list[Any] | None = None,
    ) -> QuizQuestion:
        materials = materials or []
        if not materials:
            return self.generate(topic, course_ids, count)
        first = materials[0]
        text = str(first.get("text", "")) if isinstance(first, dict) else str(first)
        heading = str(first.get("heading", "")) if isinstance(first, dict) else ""
        points = [word for word in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text.lower()) if len(word) > 4]
        expected_points = list(dict.fromkeys(points[:3])) or [topic.lower()]
        evidence_label = heading.capitalize() if heading else topic
        return QuizQuestion(
            question_id=f"quiz-{abs(hash((topic, text[:80], count))) % 100000}",
            topic=topic,
            prompt=f"Using the course evidence from {evidence_label}, explain {topic} and mention: {', '.join(expected_points)}.",
            expected_points=expected_points,
        )


class LlmQuizGenerator:
    implementation = "llm"

    def __init__(self, fallback: DeterministicQuizGenerator | None = None):
        self.fallback = fallback or DeterministicQuizGenerator()

    def generate_with_meta(
        self,
        topic: str,
        course_ids: list[str] | None = None,
        count: int = 1,
    ) -> tuple[QuizQuestion, QuizGenerationMeta]:
        prompt = (
            "Return only JSON for a quiz question with keys "
            '"question_id", "topic", "prompt", "expected_points", "difficulty". '
            f"Goal: {topic}"
        )
        try:
            raw = llm_generate([{"role": "user", "content": prompt}], settings=load_settings())
            data = json.loads(raw)
            quiz = QuizQuestion.model_validate(data)
            return quiz, QuizGenerationMeta(implementation="llm")
        except json.JSONDecodeError as exc:
            quiz = self.fallback.generate(topic, course_ids, count)
            return quiz, QuizGenerationMeta(
                implementation="deterministic-fallback",
                fallback_reason=f"JSON decode error: {exc}"[:120],
            )
        except Exception as exc:  # pragma: no cover - behavior exercised by fallback assertions
            quiz = self.fallback.generate(topic, course_ids, count)
            return quiz, QuizGenerationMeta(
                implementation="deterministic-fallback",
                fallback_reason=str(exc)[:120],
            )

    def generate(self, topic: str, course_ids: list[str] | None = None, count: int = 1) -> QuizQuestion:
        quiz, _ = self.generate_with_meta(topic, course_ids, count)
        return quiz
