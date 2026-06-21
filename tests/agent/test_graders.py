from __future__ import annotations


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
