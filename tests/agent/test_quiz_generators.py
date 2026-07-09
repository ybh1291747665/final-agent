from __future__ import annotations


def test_deterministic_quiz_generator_returns_quiz_question():
    from final_agent.agent.quiz_generators import DeterministicQuizGenerator

    quiz = DeterministicQuizGenerator().generate("review configuration management", [], 1)

    assert quiz.topic == "review configuration management"
    assert quiz.expected_points == ["review", "configuration", "management"]
    assert quiz.difficulty == "medium"


def test_llm_quiz_generator_validates_json(monkeypatch):
    from final_agent.agent.quiz_generators import LlmQuizGenerator

    monkeypatch.setattr(
        "final_agent.agent.quiz_generators.llm_generate",
        lambda messages, settings=None, model=None, temperature=None, max_tokens=None: (
            '{"question_id":"quiz-1","topic":"review CI","prompt":"What is CI?","expected_points":["automation"],"difficulty":"easy"}'
        ),
    )

    quiz, meta = LlmQuizGenerator().generate_with_meta("review CI", [], 1)

    assert quiz.prompt == "What is CI?"
    assert quiz.expected_points == ["automation"]
    assert meta.implementation == "llm"
    assert meta.fallback_reason == ""


def test_llm_quiz_generator_falls_back_to_deterministic_on_bad_json(monkeypatch):
    from final_agent.agent.quiz_generators import LlmQuizGenerator

    monkeypatch.setattr(
        "final_agent.agent.quiz_generators.llm_generate",
        lambda messages, settings=None, model=None, temperature=None, max_tokens=None: "not-json",
    )

    quiz, meta = LlmQuizGenerator().generate_with_meta("review CI", [], 1)

    assert quiz.topic == "review CI"
    assert meta.implementation == "deterministic-fallback"
    assert "json" in meta.fallback_reason.lower()


def test_select_quiz_generator_uses_llm_when_api_key_is_configured():
    from final_agent.agent.quiz_generators import LlmQuizGenerator, select_quiz_generator
    from final_agent.settings import Settings

    settings = Settings()
    settings.models_llm.api_key = "sk-live"

    generator = select_quiz_generator(settings)

    assert isinstance(generator, LlmQuizGenerator)


def test_select_quiz_generator_keeps_deterministic_without_api_key():
    from final_agent.agent.quiz_generators import DeterministicQuizGenerator, select_quiz_generator
    from final_agent.settings import Settings

    settings = Settings()
    settings.models_llm.api_key = ""

    generator = select_quiz_generator(settings)

    assert isinstance(generator, DeterministicQuizGenerator)
