from __future__ import annotations


def test_graph_creates_plan_and_waits_for_answer(monkeypatch):
    from final_agent.agent.graph import run_study_turn
    from final_agent.agent.models import AgentState

    state = run_study_turn(AgentState(session_id="s1", learning_goal="review CI"))

    assert state.status == "waiting_for_answer"
    assert [step.tool_name for step in state.plan][:2] == ["search_course_material", "generate_quiz"]
    assert state.quiz is not None
    assert [trace.tool_name for trace in state.tool_trace] == ["search_course_material", "generate_quiz"]


def test_graph_resumes_grades_and_updates_mastery():
    from final_agent.agent.graph import run_study_turn
    from final_agent.agent.models import AgentState, QuizQuestion

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        status="waiting_for_answer",
        quiz=QuizQuestion(question_id="q1", topic="review CI", prompt="Explain review CI", expected_points=["automation"]),
        learner_answer="automation matters",
    )

    updated = run_study_turn(state)

    assert updated.status == "completed"
    assert updated.grade is not None
    assert updated.grade.score == 1.0
    assert updated.tool_trace[-1].tool_name == "update_mastery"


def test_graph_fails_when_tool_limit_reached():
    from final_agent.agent.graph import run_study_turn
    from final_agent.agent.models import AgentState

    state = run_study_turn(AgentState(session_id="s1", learning_goal="review CI", tool_call_count=6))

    assert state.status == "failed"


def test_graph_module_exposes_required_node_functions():
    from final_agent.agent import graph

    required = [
        "understand_goal",
        "create_plan",
        "select_tool",
        "execute_tool",
        "request_answer",
        "grade_answer_node",
        "update_mastery_node",
        "choose_next_step",
        "finish",
    ]

    assert all(callable(getattr(graph, name, None)) for name in required)
