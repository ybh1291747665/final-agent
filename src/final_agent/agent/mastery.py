from __future__ import annotations

from typing import Literal


LearningAction = Literal["re_explain", "practice_variant", "advance_topic"]


def update_mastery_score(previous: float, latest: float) -> float:
    return min(1.0, max(0.0, round(0.7 * previous + 0.3 * latest, 6)))


def choose_learning_action(score: float) -> LearningAction:
    if score < 0.4:
        return "re_explain"
    if score <= 0.7:
        return "practice_variant"
    return "advance_topic"
