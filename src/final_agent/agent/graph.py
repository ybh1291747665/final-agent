from __future__ import annotations

from uuid import uuid4

from final_agent.agent.mastery import choose_learning_action
from final_agent.agent.models import AgentState, QuizQuestion, StudyPlanStep, ToolTraceEntry
from final_agent.agent.quiz_generators import DeterministicQuizGenerator
from final_agent.agent.tools import TOOL_REGISTRY, generate_quiz, grade_answer, run_tool, search_course_material, update_mastery


MAX_TOOL_CALLS = 6


def understand_goal(state: dict) -> dict:
    agent_state = AgentState.model_validate(state)
    agent_state.status = "running" if agent_state.status == "planning" else agent_state.status
    return agent_state.model_dump()


def create_plan(state: AgentState) -> AgentState:
    if state.plan:
        return state
    state.plan = [
        StudyPlanStep(step_id="1", objective="Find relevant course material", tool_name="search_course_material"),
        StudyPlanStep(step_id="2", objective="Generate a quiz question", tool_name="generate_quiz"),
        StudyPlanStep(step_id="3", objective="Grade the learner answer", tool_name="grade_answer"),
        StudyPlanStep(step_id="4", objective="Update mastery", tool_name="update_mastery"),
    ]
    return state


def create_plan_node(state: dict) -> dict:
    return create_plan(AgentState.model_validate(state)).model_dump()


def select_tool(state: dict) -> dict:
    agent_state = AgentState.model_validate(state)
    if agent_state.tool_call_count >= MAX_TOOL_CALLS:
        agent_state.status = "failed"
    return agent_state.model_dump()


def execute_tool(state: dict) -> dict:
    return run_study_turn(AgentState.model_validate(state)).model_dump()


def request_answer(state: dict) -> dict:
    agent_state = AgentState.model_validate(state)
    if agent_state.status != "completed":
        agent_state.status = "waiting_for_answer"
    return agent_state.model_dump()


def grade_answer_node(state: dict) -> dict:
    return run_study_turn(AgentState.model_validate(state)).model_dump()


def update_mastery_node(state: dict) -> dict:
    return state


def choose_next_step(state: dict) -> dict:
    return state


def finish(state: dict) -> dict:
    return state


def _append_trace(
    state: AgentState,
    tool_name: str,
    ok: bool,
    elapsed_ms: int,
    error: str = "",
    input_summary: str | None = None,
) -> None:
    state.tool_trace.append(ToolTraceEntry(
        tool_name=tool_name,
        input_summary=input_summary or state.learning_goal[:80],
        ok=ok,
        elapsed_ms=elapsed_ms,
        error=error,
        sequence_no=len(state.tool_trace) + 1,
    ))
    state.tool_call_count += 1


def run_study_turn(state: AgentState, repository=None, quiz_generator=None) -> AgentState:
    if state.tool_call_count >= MAX_TOOL_CALLS:
        state.status = "failed"
        return state

    quiz_generator = quiz_generator or DeterministicQuizGenerator()
    state = create_plan(state)
    for step in state.plan:
        if step.tool_name not in TOOL_REGISTRY:
            state.status = "failed"
            _append_trace(state, step.tool_name, False, 0, "Unsupported tool")
            return state

    if state.status in ("planning", "running"):
        state.status = "running"
        search_result = search_course_material(state.learning_goal, state.course_ids, 5)
        _append_trace(state, "search_course_material", search_result.ok, search_result.elapsed_ms, search_result.error)
        quiz_meta = None
        if hasattr(quiz_generator, "generate_with_meta"):
            quiz_result = run_tool(lambda: quiz_generator.generate_with_meta(state.learning_goal, state.course_ids, 1))
            if quiz_result.ok:
                state.quiz, quiz_meta = quiz_result.value
        else:
            quiz_result = generate_quiz(state.learning_goal, state.course_ids, 1, quiz_generator=quiz_generator)
            if quiz_result.ok:
                state.quiz = quiz_result.value
        _append_trace(
            state,
            "generate_quiz",
            quiz_result.ok,
            quiz_result.elapsed_ms,
            quiz_meta.fallback_reason if quiz_meta else quiz_result.error,
            input_summary=(
                f"{state.learning_goal[:60]} | impl={quiz_meta.implementation}"
                if quiz_meta
                else state.learning_goal[:80]
            ),
        )
        if not quiz_result.ok:
            state.status = "failed"
            return state
        if state.quiz is None:
            state.quiz = quiz_result.value
        state.status = "waiting_for_answer"
        return state

    if state.status == "waiting_for_answer":
        if not state.learner_answer:
            return state
        if state.quiz is None:
            state.quiz = QuizQuestion(question_id=f"quiz-{uuid4().hex[:8]}", topic=state.learning_goal, prompt=f"Explain {state.learning_goal}", expected_points=[state.learning_goal.lower()])
        grade_result = grade_answer(state.quiz.prompt, state.quiz.expected_points, state.learner_answer)
        _append_trace(state, "grade_answer", grade_result.ok, grade_result.elapsed_ms, grade_result.error)
        if not grade_result.ok:
            state.status = "failed"
            return state
        state.grade = grade_result.value
        if repository is not None:
            repository.save_attempt(state.session_id, state.quiz, state.learner_answer, state.grade)
        mastery_result = update_mastery(state.session_id, state.quiz.topic, state.grade.score, repository)
        _append_trace(state, "update_mastery", mastery_result.ok, mastery_result.elapsed_ms, mastery_result.error)
        if not mastery_result.ok:
            state.status = "failed"
            return state
        state.next_action = choose_learning_action(state.grade.score)
        state.status = "completed"
        return state

    return state


def build_graph(checkpointer=None):
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return None

    graph = StateGraph(dict)
    graph.add_node("understand_goal", understand_goal)
    graph.add_node("create_plan", create_plan_node)
    graph.add_node("select_tool", select_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("request_answer", request_answer)
    graph.add_node("grade_answer", grade_answer_node)
    graph.add_node("update_mastery", update_mastery_node)
    graph.add_node("choose_next_step", choose_next_step)
    graph.add_node("finish", finish)
    graph.set_entry_point("understand_goal")
    graph.add_edge("understand_goal", "create_plan")
    graph.add_edge("create_plan", "select_tool")
    graph.add_edge("select_tool", "execute_tool")
    graph.add_edge("execute_tool", "request_answer")
    graph.add_edge("request_answer", "grade_answer")
    graph.add_edge("grade_answer", "update_mastery")
    graph.add_edge("update_mastery", "choose_next_step")
    graph.add_edge("choose_next_step", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()
