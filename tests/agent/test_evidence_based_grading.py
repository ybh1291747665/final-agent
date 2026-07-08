from __future__ import annotations


def test_deterministic_grader_feedback_mentions_missing_evidence_point():
    from final_agent.agent.graders import DeterministicGrader

    grade = DeterministicGrader().grade(
        "Explain CI.",
        ["automated", "tests"],
        "CI means automated builds.",
        materials=[
            {
                "heading": "Continuous Integration",
                "text": "Continuous integration runs automated builds and tests after each change.",
            }
        ],
    )

    assert grade.score == 0.5
    assert grade.covered_points == ["automated"]
    assert grade.missed_points == ["tests"]
    assert "course evidence" in grade.feedback
    assert "tests" in grade.feedback
