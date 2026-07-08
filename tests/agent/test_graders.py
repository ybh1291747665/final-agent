from __future__ import annotations

from final_agent.settings import Settings


def assert_deterministic_partial_grade(grade):
    assert grade.score == 0.5
    assert grade.covered_points == ["automation"]
    assert grade.missed_points == ["testing"]
    assert grade.feedback == "Review: testing"


def make_settings() -> Settings:
    return Settings()


def test_deterministic_grader_matches_expected_points():
    from final_agent.agent.graders import DeterministicGrader

    grade = DeterministicGrader().grade(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds and testing.",
        materials=[],
    )

    assert grade.score == 1.0
    assert grade.covered_points == ["automation", "testing"]
    assert grade.missed_points == []
    assert grade.feedback == "Covered all expected points from the course evidence."


def test_deterministic_grader_does_not_match_common_prefix_only():
    from final_agent.agent.graders import DeterministicGrader

    grade = DeterministicGrader().grade(
        "What is CI?",
        ["automation"],
        "An automobile needs fuel.",
        materials=[],
    )

    assert grade.score == 0.0
    assert grade.covered_points == []
    assert grade.missed_points == ["automation"]
    assert grade.feedback == "Review: automation"


def test_llm_grader_validates_json():
    from final_agent.agent.graders import LlmGrader

    grade, meta = LlmGrader(
        llm_callable=lambda messages, settings=None, model=None, temperature=None, max_tokens=None: (
            '{"score":0.5,"covered_points":["automation"],"missed_points":["testing"],"feedback":"Mention testing too."}'
        ),
        settings=make_settings(),
    ).grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert grade.score == 0.5
    assert grade.covered_points == ["automation"]
    assert grade.missed_points == ["testing"]
    assert meta.implementation == "llm"
    assert meta.fallback_reason == ""


def test_llm_grader_falls_back_to_deterministic_on_bad_json():
    from final_agent.agent.graders import LlmGrader

    grade, meta = LlmGrader(
        llm_callable=lambda messages, settings=None, model=None, temperature=None, max_tokens=None: "not-json",
        settings=make_settings(),
    ).grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert_deterministic_partial_grade(grade)
    assert meta.implementation == "deterministic-fallback"
    assert "json" in meta.fallback_reason.lower()


def test_llm_grader_falls_back_to_deterministic_on_provider_exception():
    from final_agent.agent.graders import LlmGrader

    grade, meta = LlmGrader(
        llm_callable=lambda messages, settings=None, model=None, temperature=None, max_tokens=None: (_ for _ in ()).throw(
            RuntimeError("provider offline")
        ),
        settings=make_settings(),
    ).grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert_deterministic_partial_grade(grade)
    assert meta.implementation == "deterministic-fallback"
    assert "provider offline" in meta.fallback_reason.lower()


def test_llm_grader_falls_back_to_deterministic_on_validation_failure():
    from final_agent.agent.graders import LlmGrader

    grade, meta = LlmGrader(
        llm_callable=lambda messages, settings=None, model=None, temperature=None, max_tokens=None: (
            '{"score":0.5,"covered_points":["automation"],"missed_points":["testing"]}'
        ),
        settings=make_settings(),
    ).grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert_deterministic_partial_grade(grade)
    assert meta.implementation == "deterministic-fallback"
    assert meta.fallback_reason.startswith("Validation error:")


def test_llm_grader_uses_settings_loader_when_settings_not_injected():
    from final_agent.agent.graders import LlmGrader

    captured = {}
    loaded_settings = make_settings()

    grade, meta = LlmGrader(
        llm_callable=lambda messages, settings=None, model=None, temperature=None, max_tokens=None: captured.setdefault(
            "settings", settings
        )
        and '{"score":1.0,"covered_points":["automation"],"missed_points":[],"feedback":"ok"}',
        settings_loader=lambda: loaded_settings,
    ).grade_with_meta(
        "What is CI?",
        ["automation"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert captured["settings"] is loaded_settings
    assert isinstance(captured["settings"], Settings)
    assert grade.score == 1.0
    assert meta.implementation == "llm"
