from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_agent_state_validates_status_and_tool_call_limit():
    from final_agent.agent.models import AgentState

    state = AgentState(session_id="s1", learning_goal="review pipelines", tool_call_count=6)

    assert state.status == "planning"
    with pytest.raises(ValidationError):
        AgentState(session_id="s1", learning_goal="review pipelines", tool_call_count=7)
    with pytest.raises(ValidationError):
        AgentState(session_id="s1", learning_goal="review pipelines", status="unknown")


def test_quiz_and_grade_models_round_trip():
    from final_agent.agent.models import GradeResult, QuizQuestion

    quiz = QuizQuestion(question_id="q1", topic="CI", prompt="What is CI?", expected_points=["automation"])
    grade = GradeResult(score=1.0, covered_points=["automation"], missed_points=[], feedback="Good")

    assert QuizQuestion.model_validate_json(quiz.model_dump_json()).topic == "CI"
    assert GradeResult.model_validate_json(grade.model_dump_json()).score == 1.0
