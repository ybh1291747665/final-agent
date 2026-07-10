from __future__ import annotations


def test_agent_roles_have_fixed_stage_one_sequence():
    from final_agent.agent.roles import AgentRole, ROLE_SEQUENCE

    assert ROLE_SEQUENCE == [
        AgentRole.SUPERVISOR,
        AgentRole.RETRIEVAL,
        AgentRole.QUIZ,
        AgentRole.GRADER,
        AgentRole.COACH,
        AgentRole.CRITIC,
    ]


def test_agent_roles_define_allowed_tools():
    from final_agent.agent.roles import AgentRole, allowed_tools_for_role

    assert allowed_tools_for_role(AgentRole.SUPERVISOR) == []
    assert allowed_tools_for_role(AgentRole.RETRIEVAL) == ["search_course_material", "summarize_course"]
    assert allowed_tools_for_role(AgentRole.QUIZ) == ["generate_quiz"]
    assert allowed_tools_for_role(AgentRole.GRADER) == ["grade_answer"]
    assert allowed_tools_for_role(AgentRole.COACH) == ["get_learning_profile", "update_mastery"]
    assert allowed_tools_for_role(AgentRole.CRITIC) == [
        "verify_evidence",
        "verify_grade_consistency",
        "verify_answer_quality",
    ]


def test_agent_state_carries_multi_agent_fields():
    from final_agent.agent.models import AgentState

    state = AgentState(session_id="s1", learning_goal="review CI")

    assert state.agent_plan == []
    assert state.agent_trace == []
    assert state.critic_warnings == []
    assert state.quality_report is None
    assert state.current_agent_role == ""
