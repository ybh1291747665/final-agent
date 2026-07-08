from __future__ import annotations


def test_verify_evidence_warns_when_quiz_has_no_materials():
    from final_agent.agent.critics import verify_evidence

    warnings = verify_evidence(quiz_prompt="Explain CI.", evidence_count=0)

    assert [warning.code for warning in warnings] == ["missing_evidence"]


def test_verify_grade_consistency_warns_when_next_action_conflicts_with_score():
    from final_agent.agent.critics import verify_grade_consistency

    warnings = verify_grade_consistency(score=0.2, next_action="advance_topic")

    assert [warning.code for warning in warnings] == ["next_action_score_mismatch"]


def test_verify_grade_consistency_accepts_matching_score_and_action():
    from final_agent.agent.critics import verify_grade_consistency

    assert verify_grade_consistency(score=0.9, next_action="advance_topic") == []
