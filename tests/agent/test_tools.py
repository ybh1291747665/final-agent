from __future__ import annotations


def test_grade_answer_uses_expected_point_coverage():
    from final_agent.agent.tools import grade_answer

    result = grade_answer("What is CI?", ["automation", "testing"], "CI is automation for builds and testing.")

    assert result.ok is True
    assert result.value.score == 1.0
    assert result.value.covered_points == ["automation", "testing"]


def test_tool_result_converts_recoverable_errors():
    from final_agent.agent.tools import run_tool

    result = run_tool(lambda: (_ for _ in ()).throw(RuntimeError("temporary failure")))

    assert result.ok is False
    assert "temporary failure" in result.error
    assert result.elapsed_ms >= 0


def test_search_tool_calls_retrieval_pipeline(monkeypatch, sample_chunks):
    from final_agent.agent import tools

    calls = {}

    def fake_search(query, settings=None, *, top_k=None, course_ids=None):
        calls.update(query=query, top_k=top_k, course_ids=course_ids)
        return sample_chunks

    monkeypatch.setattr(tools.retrieval_pipeline, "search", fake_search)

    result = tools.search_course_material("pipeline", ["course-a"], 2)

    assert result.ok is True
    assert calls == {"query": "pipeline", "top_k": 2, "course_ids": ["course-a"]}
    assert len(result.value) == 3


def test_generate_quiz_delegates_to_injected_generator():
    from final_agent.agent.models import QuizQuestion
    from final_agent.agent.tools import generate_quiz

    class FakeGenerator:
        def generate(self, topic, course_ids=None, count=1):
            return QuizQuestion(
                question_id="quiz-x",
                topic=topic,
                prompt="Injected prompt",
                expected_points=["adapter"],
                difficulty="hard",
            )

    result = generate_quiz("review CI", ["course-a"], 1, quiz_generator=FakeGenerator())

    assert result.ok is True
    assert result.value.prompt == "Injected prompt"
    assert result.value.difficulty == "hard"


def test_grade_answer_delegates_to_injected_grader():
    from final_agent.agent.models import GradeResult
    from final_agent.agent.tools import grade_answer

    class FakeGrader:
        def grade(self, question, expected_points, learner_answer, *, materials=None):
            return GradeResult(
                score=0.25,
                covered_points=["adapter"],
                missed_points=["testing"],
                feedback="Injected grade",
            )

    result = grade_answer(
        "What is CI?",
        ["automation", "testing"],
        "adapter",
        grader=FakeGrader(),
        materials=[],
    )

    assert result.ok is True
    assert result.value.score == 0.25
    assert result.value.feedback == "Injected grade"
