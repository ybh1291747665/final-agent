from __future__ import annotations


def assert_deterministic_partial_grade(grade):
    assert grade.score == 0.5
    assert grade.covered_points == ["automation"]
    assert grade.missed_points == ["testing"]
    assert grade.feedback == "Review: testing"


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
    assert grade.feedback == "Covered all expected points."


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
        settings={"provider": "test"},
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
        settings={"provider": "test"},
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
        settings={"provider": "test"},
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
        settings={"provider": "test"},
    ).grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert_deterministic_partial_grade(grade)
    assert meta.implementation == "deterministic-fallback"
    assert "feedback" in meta.fallback_reason.lower()
