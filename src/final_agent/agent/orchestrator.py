from __future__ import annotations

from uuid import uuid4

from final_agent.agent.critics import evaluate_answer_quality
from final_agent.agent.evidence_reuse import EvidenceReusePolicy
from final_agent.agent.evidence import build_budgeted_transient_materials, build_evidence_packet, summarize_evidence_for_trace
from final_agent.agent.mastery import choose_learning_action
from final_agent.agent.models import AgentState, AgentToolTraceEntry, CriticWarning, QuizQuestion, StudyPlanStep, ToolCall, ToolResult
from final_agent.agent.roles import AgentRole, ROLE_SEQUENCE, allowed_tools_for_role
from final_agent.agent.tool_registry import ToolRegistry, build_default_tool_registry
from final_agent.memory.resolver import MemoryResolver
from final_agent.schemas import Chunk, ScoredChunk
from final_agent.token_budget import TokenBudgeter


class MultiAgentOrchestrator:
    def __init__(self, repository=None, quiz_generator=None, grader=None, registry: ToolRegistry | None = None):
        self.repository = repository
        self.registry = registry or build_default_tool_registry(
            repository=repository,
            quiz_generator=quiz_generator,
            grader=grader,
        )
        self.reuse_policy = EvidenceReusePolicy()
        self.budgeter = TokenBudgeter()
        self.memory_resolver = MemoryResolver(repository, self.budgeter) if repository is not None else None

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
            input_summary=self._summarize_input(call),
            output_summary=self._summarize_output(result.value) if result.ok else "",
        )
        return result

    def _summarize_input(self, call: ToolCall) -> str:
        arguments = dict(call.arguments)
        materials = arguments.get("materials")
        if isinstance(materials, list):
            arguments["materials"] = f"{len(materials)} materials"
        if "learner_answer" in arguments:
            arguments["learner_answer"] = str(arguments["learner_answer"])[:80]
        return str(arguments)[:120]

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

    def _memory_materials(self, state: AgentState) -> list[dict]:
        if self.memory_resolver is None:
            return []
        resolved = self.memory_resolver.resolve(
            session_id=state.session_id,
            topic=state.learning_goal,
            course_ids=state.course_ids,
            budget=state.evidence_packet.budget if state.evidence_packet is not None else None,
        )
        content = str(resolved.get("content", "")).strip()
        if not content:
            return []
        return [
            {
                "chunk_id": f"memory:{state.session_id}",
                "doc_id": "memory",
                "source_path": "memory",
                "page_num": None,
                "heading": "Conversation memory",
                "text": content,
                "score": 0.0,
                "retrieval_source": "memory",
            }
        ]

    def _scored_chunks_from_packet(self, state: AgentState) -> list[ScoredChunk]:
        packet = state.evidence_packet
        if packet is None:
            return []
        chunks_by_id: dict[str, Chunk] = {}
        try:
            from final_agent.knowledge.vector_store import get_chunks_by_ids

            chunks = get_chunks_by_ids(packet.retrieved_chunk_ids, course_ids=packet.course_ids)
            chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        except Exception:
            chunks_by_id = {}
        fallback = {snapshot.chunk_id: snapshot for snapshot in packet.evidence_snapshots}
        scored: list[ScoredChunk] = []
        for chunk_id in packet.retrieved_chunk_ids:
            chunk = chunks_by_id.get(chunk_id)
            snapshot = fallback.get(chunk_id)
            if chunk is None and snapshot is not None:
                chunk = Chunk(
                    chunk_id=snapshot.chunk_id,
                    doc_id=snapshot.doc_id,
                    text=snapshot.summary,
                    heading_path=[snapshot.heading] if snapshot.heading else [],
                    page_num=snapshot.page_num,
                    metadata={"source_path": snapshot.source_path},
                )
            if chunk is None:
                continue
            scored.append(
                ScoredChunk(
                    chunk=chunk,
                    score=(snapshot.score if snapshot is not None else 0.0),
                    source="reused",
                )
            )
        return scored

    def _update_session_summary(self, state: AgentState) -> None:
        grade_score = state.grade.score if state.grade is not None else 0.0
        feedback = state.grade.feedback if state.grade is not None else ""
        turn = (
            f"Turn {state.turn_index + 1}: goal={state.learning_goal}; "
            f"answer={state.learner_answer}; score={grade_score:.2f}; "
            f"next={state.next_action}; feedback={feedback}"
        )
        combined = "\n".join(part for part in [state.session_summary, turn] if part)
        state.session_summary = self.budgeter.truncate_to_tokens(combined, 1200)
        if self.repository is not None:
            self.repository.upsert_memory_item(
                scope="session",
                scope_id=state.session_id,
                kind="session_summary",
                content=state.session_summary,
                token_count=self.budgeter.count_tokens(state.session_summary),
                metadata={"turn_index": state.turn_index + 1},
            )
            if state.grade is not None and state.grade.score < 0.7:
                self.repository.upsert_memory_item(
                    scope="topic",
                    scope_id=state.quiz.topic if state.quiz else state.learning_goal,
                    kind="topic_memory",
                    content=feedback or state.learning_goal,
                    token_count=self.budgeter.count_tokens(feedback or state.learning_goal),
                    metadata={"session_id": state.session_id, "score": grade_score},
                )
            for course_id in state.course_ids:
                self.repository.upsert_memory_item(
                    scope="course",
                    scope_id=course_id,
                    kind="course_memory",
                    content=f"Latest reviewed topic: {state.learning_goal}; next action: {state.next_action}",
                    token_count=self.budgeter.count_tokens(state.learning_goal) + 8,
                    metadata={"session_id": state.session_id},
                )

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
            decision = self.reuse_policy.decide(
                query=state.learning_goal,
                course_ids=state.course_ids,
                reading_context=state.reading_context,
                previous_packet=state.evidence_packet,
                quality_report=state.quality_report,
                current_turn=state.turn_index,
            )
            materials: list[dict] = []
            state.evidence_snapshots = []
            if decision.reuse:
                state.retrieval_decision = decision.trace_value
                reused_results = self._scored_chunks_from_packet(state)
                if reused_results:
                    state.evidence_snapshots = state.evidence_packet.evidence_snapshots if state.evidence_packet else []
                    materials = build_budgeted_transient_materials(
                        reused_results,
                        budget=state.evidence_packet.budget if state.evidence_packet else None,
                        budgeter=self.budgeter,
                    )
                    self._append_trace(
                        state,
                        AgentRole.RETRIEVAL,
                        ToolResult(ok=True, value=reused_results),
                        tool_name="search_course_material",
                        input_summary=f"reuse:{decision.reason}",
                        output_summary="reused evidence packet",
                    )
                else:
                    decision = decision.__class__(False, "reused_chunks_unavailable")
            if not decision.reuse:
                state.retrieval_decision = decision.trace_value
                retrieval = self._execute(
                    state,
                    AgentRole.RETRIEVAL,
                    ToolCall(
                        name="search_course_material",
                        arguments={
                            "query": state.learning_goal,
                            "course_ids": state.course_ids,
                            "top_k": 5,
                            "reading_context": state.reading_context,
                        },
                    ),
                )
                if retrieval.ok:
                    packet = build_evidence_packet(
                        state.learning_goal,
                        retrieval.value,
                        course_ids=state.course_ids,
                        reading_context=state.reading_context,
                        created_turn=state.turn_index,
                        budgeter=self.budgeter,
                    )
                    state.evidence_packet = packet
                    state.evidence_snapshots = packet.evidence_snapshots
                    materials = build_budgeted_transient_materials(
                        retrieval.value,
                        budget=packet.budget,
                        budgeter=self.budgeter,
                    )
                    if len(state.agent_trace) >= 2:
                        state.agent_trace[-1].output_summary = summarize_evidence_for_trace(state.evidence_snapshots)
            elif len(state.agent_trace) >= 2:
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
                        "materials": materials + self._memory_materials(state),
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
            answer_quality = self._execute(
                state,
                AgentRole.CRITIC,
                ToolCall(
                    name="verify_answer_quality",
                    arguments={"answer": state.learner_answer, "evidence": state.evidence_snapshots},
                ),
            )
            warnings: list[CriticWarning] = []
            if evidence.ok:
                warnings.extend(evidence.value)
            if consistency.ok:
                warnings.extend(consistency.value)
            if answer_quality.ok:
                warnings.extend(answer_quality.value)
                state.quality_report = evaluate_answer_quality(state.learner_answer, state.evidence_snapshots)
            state.critic_warnings = warnings
            self._update_session_summary(state)
            state.turn_index += 1
            state.status = "completed"
            return state

        return state
