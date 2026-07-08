from __future__ import annotations

from final_agent.agent.models import CriticWarning


def verify_evidence(*, quiz_prompt: str, evidence_count: int) -> list[CriticWarning]:
    if quiz_prompt and evidence_count <= 0:
        return [
            CriticWarning(
                code="missing_evidence",
                message="Quiz was generated without retrieved course evidence.",
            )
        ]
    return []


def verify_grade_consistency(*, score: float, next_action: str) -> list[CriticWarning]:
    if score < 0.4 and next_action != "re_explain":
        return [
            CriticWarning(
                code="next_action_score_mismatch",
                message="Low score should usually lead to re_explain.",
            )
        ]
    if score > 0.7 and next_action != "advance_topic":
        return [
            CriticWarning(
                code="next_action_score_mismatch",
                message="High score should usually lead to advance_topic.",
            )
        ]
    return []
