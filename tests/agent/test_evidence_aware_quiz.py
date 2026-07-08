from __future__ import annotations

import os
import subprocess
import sys


def test_generate_quiz_accepts_transient_materials():
    from final_agent.agent.tools import generate_quiz

    materials = [
        {
            "heading": "Continuous Integration",
            "text": "Continuous integration runs automated builds and tests after each change.",
        }
    ]

    result = generate_quiz("review CI", [], 1, materials=materials)

    assert result.ok is True
    assert result.value.topic == "review CI"
    assert "Continuous Integration" in result.value.prompt
    assert "automated" in result.value.expected_points


def test_generate_quiz_input_schema_carries_materials():
    from final_agent.agent.tools import GenerateQuizInput

    payload = GenerateQuizInput.model_validate(
        {
            "topic": "review CI",
            "course_ids": [],
            "count": 1,
            "materials": [{"text": "CI runs tests."}],
        }
    )

    assert payload.materials == [{"text": "CI runs tests."}]


def test_default_registry_forwards_materials_to_quiz_generator():
    from final_agent.agent.models import QuizQuestion, ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import build_default_tool_registry

    calls = {}

    class FakeGenerator:
        def generate_with_evidence(self, topic, course_ids=None, count=1, *, materials=None):
            calls["materials"] = materials
            return QuizQuestion(
                question_id="q1",
                topic=topic,
                prompt="Evidence quiz",
                expected_points=["evidence"],
            )

    registry = build_default_tool_registry(quiz_generator=FakeGenerator())
    result = registry.execute(
        AgentRole.QUIZ,
        ToolCall(
            name="generate_quiz",
            arguments={
                "topic": "review CI",
                "course_ids": [],
                "count": 1,
                "materials": [{"text": "CI runs tests."}],
            },
        ),
        allowed_tools=["generate_quiz"],
    )

    assert result.ok is True
    assert calls["materials"] == [{"text": "CI runs tests."}]


def test_generate_quiz_with_evidence_uses_stable_question_id():
    script = (
        "from final_agent.agent.quiz_generators import DeterministicQuizGenerator;"
        "materials = [{'heading': 'CI', 'text': 'Continuous integration runs automated builds and tests.'}];"
        "quiz = DeterministicQuizGenerator().generate_with_evidence('review CI', [], 1, materials=materials);"
        "print(quiz.question_id)"
    )

    first = _question_id_from_subprocess(script, hash_seed="1")
    second = _question_id_from_subprocess(script, hash_seed="2")

    assert first == second


def _question_id_from_subprocess(script: str, *, hash_seed: str) -> str:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    return result.stdout.strip()
