from __future__ import annotations


def test_orchestrator_initial_turn_runs_supervisor_retrieval_and_quiz():
    from final_agent.agent.models import AgentState
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.roles import AgentRole

    state = MultiAgentOrchestrator().run_turn(AgentState(session_id="s1", learning_goal="review CI"))

    assert state.status == "waiting_for_answer"
    assert state.quiz is not None
    assert [entry.agent_role for entry in state.agent_trace] == [
        AgentRole.SUPERVISOR,
        AgentRole.RETRIEVAL,
        AgentRole.QUIZ,
    ]
    assert state.agent_trace[0].output_summary == "Plan ready"
    assert state.agent_trace[1].tool_name == "search_course_material"
    assert state.agent_trace[2].tool_name == "generate_quiz"


def test_orchestrator_answer_turn_runs_grader_coach_and_critic():
    from final_agent.agent.models import AgentState, QuizQuestion
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.roles import AgentRole

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        quiz=QuizQuestion(
            question_id="q1",
            topic="review CI",
            prompt="Explain CI.",
            expected_points=["automation"],
        ),
        learner_answer="I am not sure.",
        status="waiting_for_answer",
    )

    state = MultiAgentOrchestrator().run_turn(state)

    assert state.status == "completed"
    assert state.grade is not None
    assert state.next_action == "re_explain"
    assert [entry.agent_role for entry in state.agent_trace] == [
        AgentRole.GRADER,
        AgentRole.COACH,
        AgentRole.CRITIC,
        AgentRole.CRITIC,
    ]
    assert [warning.code for warning in state.critic_warnings] == ["missing_evidence"]
