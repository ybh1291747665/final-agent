from __future__ import annotations

from uuid import uuid4

from final_agent.agent.evidence import build_evidence_snapshots, build_transient_materials, summarize_evidence_for_trace
from final_agent.agent.mastery import choose_learning_action
from final_agent.agent.models import AgentState, AgentToolTraceEntry, CriticWarning, QuizQuestion, StudyPlanStep, ToolCall, ToolResult
from final_agent.agent.roles import AgentRole, ROLE_SEQUENCE, allowed_tools_for_role
from final_agent.agent.tool_registry import ToolRegistry, build_default_tool_registry


class MultiAgentOrchestrator:
    def __init__(self, repository=None, quiz_generator=None, grader=None, registry: ToolRegistry | None = None):
        self.repository = repository
        self.registry = registry or build_default_tool_registry(
            repository=repository,
            quiz_generator=quiz_generator,
            grader=grader,
        )

    def _ensure_agent_plan(self, state: AgentState) -> None:
        if not state.agent_plan:
            state.agent_plan = [role.value for role in ROLE_SEQUENCE]
        if state.plan:
            return
        state.plan = [
            StudyPlanStep(step_id="1", objective="Find relevant course material", tool_name="search_course_material"),
            StudyPlanStep(step_id="2", objective="Generate a quiz question", tool_name="generate_quiz"),
            StudyPlanStep(step_id="3", objective="Grade the learner answer", tool_name="grade_answer"),
            StudyPlanStep(step_id="4", objective="Update mastery", tool_name="update_mastery"),
        ]

    def _append_trace(
        self,
        state: AgentState,
        role: AgentRole,
        result: ToolResult,
        *,
        tool_name: str = "",
        input_summary: str = "",
        output_summary: str = "",
        fallback_reason: str = "",
    ) -> None:
        state.agent_trace.append(
            AgentToolTraceEntry(
                agent_role=role,
                tool_name=tool_name,
                input_summary=input_summary,
                output_summary=output_summary,
                ok=result.ok,
                elapsed_ms=result.elapsed_ms,
                error=result.error,
                fallback_reason=fallback_reason,
                sequence_no=len(state.agent_trace) + 1,
            )
        )

    def _execute(self, state: AgentState, role: AgentRole, call: ToolCall) -> ToolResult:
        state.current_agent_role = role.value
        result = self.registry.execute(role, call, allowed_tools=allowed_tools_for_role(role))
        self._append_trace(
            state,
            role,
            result,
            tool_name=call.name,
            input_summary=str(call.arguments)[:120],
            output_summary=self._summarize_output(result.value) if result.ok else "",
        )
        return result

    def _summarize_output(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return f"{len(value)} items"
        if isinstance(value, dict):
            return f"{len(value)} entries"
        if hasattr(value, "prompt"):
            return str(value.prompt)[:120]
        if hasattr(value, "score"):
            return f"score={value.score}"
        if hasattr(value, "attempts"):
            return f"attempts={value.attempts}"
        return str(value)[:120]

    def _materials_from_snapshots(self, state: AgentState) -> list[dict]:
        return [
            {
                "chunk_id": snapshot.chunk_id,
                "doc_id": snapshot.doc_id,
                "source_path": snapshot.source_path,
                "page_num": snapshot.page_num,
                "heading": snapshot.heading,
                "text": snapshot.summary,
                "score": snapshot.score,
                "retrieval_source": snapshot.retrieval_source,
            }
            for snapshot in state.evidence_snapshots
        ]

    def run_turn(self, state: AgentState) -> AgentState:
        self._ensure_agent_plan(state)

        if state.status in ("planning", "running"):
            state.status = "running"
            self._append_trace(
                state,
                AgentRole.SUPERVISOR,
                ToolResult(ok=True),
                output_summary="Plan ready",
            )
            retrieval = self._execute(
                state,
                AgentRole.RETRIEVAL,
                ToolCall(
                    name="search_course_material",
                    arguments={"query": state.learning_goal, "course_ids": state.course_ids, "top_k": 5},
                ),
            )
            materials: list[dict] = []
            state.evidence_snapshots = []
            if retrieval.ok:
                state.evidence_snapshots = build_evidence_snapshots(retrieval.value, limit=3)
                materials = build_transient_materials(retrieval.value, limit=3)
                if len(state.agent_trace) >= 2:
                    state.agent_trace[-1].output_summary = summarize_evidence_for_trace(state.evidence_snapshots)
            quiz = self._execute(
                state,
                AgentRole.QUIZ,
                ToolCall(
                    name="generate_quiz",
                    arguments={
                        "topic": state.learning_goal,
                        "course_ids": state.course_ids,
                        "count": 1,
                        "materials": materials,
                    },
                ),
            )
            if not quiz.ok:
                state.status = "failed"
                return state
            state.quiz = quiz.value
            state.status = "waiting_for_answer"
            return state

        if state.status == "waiting_for_answer":
            if not state.learner_answer:
                return state
            if state.quiz is None:
                state.quiz = QuizQuestion(
                    question_id=f"quiz-{uuid4().hex[:8]}",
                    topic=state.learning_goal,
                    prompt=f"Explain {state.learning_goal}",
                    expected_points=[state.learning_goal.lower()],
                )
            grade = self._execute(
                state,
                AgentRole.GRADER,
                ToolCall(
                    name="grade_answer",
                    arguments={
                        "question": state.quiz.prompt,
                        "expected_points": state.quiz.expected_points,
                        "learner_answer": state.learner_answer,
                        "materials": self._materials_from_snapshots(state),
                    },
                ),
            )
            if not grade.ok:
                state.status = "failed"
                return state
            state.grade = grade.value
            if self.repository is not None:
                self.repository.save_attempt(state.session_id, state.quiz, state.learner_answer, state.grade)
            state.next_action = choose_learning_action(state.grade.score)
            mastery = self._execute(
                state,
                AgentRole.COACH,
                ToolCall(
                    name="update_mastery",
                    arguments={"session_id": state.session_id, "topic": state.quiz.topic, "score": state.grade.score},
                ),
            )
            if not mastery.ok:
                state.status = "failed"
                return state
            evidence = self._execute(
                state,
                AgentRole.CRITIC,
                ToolCall(
                    name="verify_evidence",
                    arguments={"quiz_prompt": state.quiz.prompt, "evidence_count": len(state.evidence_snapshots)},
                ),
            )
            consistency = self._execute(
                state,
                AgentRole.CRITIC,
                ToolCall(
                    name="verify_grade_consistency",
                    arguments={"score": state.grade.score, "next_action": state.next_action},
                ),
            )
            warnings: list[CriticWarning] = []
            if evidence.ok:
                warnings.extend(evidence.value)
            if consistency.ok:
                warnings.extend(consistency.value)
            state.critic_warnings = warnings
            state.status = "completed"
            return state

        return state
