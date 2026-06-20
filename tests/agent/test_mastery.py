from __future__ import annotations


def test_mastery_score_is_weighted_and_clamped():
    from final_agent.agent.mastery import update_mastery_score

    assert update_mastery_score(0.5, 1.0) == 0.65
    assert update_mastery_score(2.0, 2.0) == 1.0
    assert update_mastery_score(-1.0, -1.0) == 0.0


def test_learning_action_thresholds():
    from final_agent.agent.mastery import choose_learning_action

    assert choose_learning_action(0.39) == "re_explain"
    assert choose_learning_action(0.4) == "practice_variant"
    assert choose_learning_action(0.7) == "practice_variant"
    assert choose_learning_action(0.71) == "advance_topic"
