from __future__ import annotations

from enum import StrEnum


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    RETRIEVAL = "retrieval"
    QUIZ = "quiz"
    GRADER = "grader"
    COACH = "coach"
    CRITIC = "critic"


ROLE_SEQUENCE: list[AgentRole] = [
    AgentRole.SUPERVISOR,
    AgentRole.RETRIEVAL,
    AgentRole.QUIZ,
    AgentRole.GRADER,
    AgentRole.COACH,
    AgentRole.CRITIC,
]


ROLE_ALLOWED_TOOLS: dict[AgentRole, list[str]] = {
    AgentRole.SUPERVISOR: [],
    AgentRole.RETRIEVAL: ["search_course_material", "summarize_course"],
    AgentRole.QUIZ: ["generate_quiz"],
    AgentRole.GRADER: ["grade_answer"],
    AgentRole.COACH: ["get_learning_profile", "update_mastery"],
    AgentRole.CRITIC: ["verify_evidence", "verify_grade_consistency"],
}


def allowed_tools_for_role(role: AgentRole) -> list[str]:
    return list(ROLE_ALLOWED_TOOLS[role])
