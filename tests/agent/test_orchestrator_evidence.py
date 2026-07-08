from __future__ import annotations


def test_initial_turn_carries_top_three_retrieval_results_to_quiz_and_trace():
    from final_agent.agent.models import AgentState, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator

    calls = []

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            calls.append(call)
            if call.name == "search_course_material":
                return ToolResult(ok=True, value=[_scored_chunk(index) for index in range(4)])
            if call.name == "generate_quiz":
                materials = call.arguments["materials"]
                return ToolResult(
                    ok=True,
                    value=QuizQuestion(
                        question_id="q1",
                        topic=call.arguments["topic"],
                        prompt=f"Quiz generated from {len(materials)} evidence items.",
                        expected_points=["evidence"],
                    ),
                )
            raise AssertionError(f"Unexpected tool call: {call.name}")

    state = MultiAgentOrchestrator(registry=FakeRegistry()).run_turn(
        AgentState(session_id="s1", learning_goal="review CI")
    )

    quiz_call = calls[1]
    assert state.status == "waiting_for_answer"
    assert [snapshot.chunk_id for snapshot in state.evidence_snapshots] == ["chunk-0", "chunk-1", "chunk-2"]
    assert len(quiz_call.arguments["materials"]) == 3
    assert quiz_call.arguments["materials"][0]["text"] == "Full text for chunk 0."
    assert state.quiz is not None
    assert "3 evidence items" in state.quiz.prompt
    assert state.agent_trace[1].output_summary == "3 evidence snapshots"


def test_answer_turn_rebuilds_grader_materials_from_snapshots_and_counts_critic_evidence():
    from final_agent.agent.models import AgentState, EvidenceSnapshot, GradeResult, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.roles import AgentRole

    calls = []

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            calls.append((role, call))
            if call.name == "grade_answer":
                return ToolResult(ok=True, value=GradeResult(score=0.8, feedback="Good."))
            if call.name == "update_mastery":
                return ToolResult(ok=True, value=None)
            if call.name in {"verify_evidence", "verify_grade_consistency"}:
                return ToolResult(ok=True, value=[])
            raise AssertionError(f"Unexpected tool call: {call.name}")

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        quiz=QuizQuestion(
            question_id="q1",
            topic="review CI",
            prompt="Explain CI.",
            expected_points=["automation"],
        ),
        learner_answer="CI automates checks.",
        status="waiting_for_answer",
        evidence_snapshots=[
            EvidenceSnapshot(
                chunk_id="chunk-1",
                doc_id="doc-1",
                source_path="slides/week1.pdf",
                page_num=7,
                heading="CI",
                summary="Compact evidence summary.",
                score=0.91,
                retrieval_source="rrf",
            )
        ],
    )

    state = MultiAgentOrchestrator(registry=FakeRegistry()).run_turn(state)

    grade_call = calls[0][1]
    evidence_call = next(call for role, call in calls if role == AgentRole.CRITIC and call.name == "verify_evidence")
    assert state.status == "completed"
    assert grade_call.arguments["materials"] == [
        {
            "chunk_id": "chunk-1",
            "doc_id": "doc-1",
            "source_path": "slides/week1.pdf",
            "page_num": 7,
            "heading": "CI",
            "text": "Compact evidence summary.",
            "score": 0.91,
            "retrieval_source": "rrf",
        }
    ]
    assert evidence_call.arguments["evidence_count"] == 1


def test_initial_turn_clears_stale_evidence_when_retrieval_fails():
    from final_agent.agent.models import AgentState, EvidenceSnapshot, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator

    calls = []

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            calls.append(call)
            if call.name == "search_course_material":
                return ToolResult(ok=False, error="search unavailable")
            if call.name == "generate_quiz":
                return ToolResult(
                    ok=True,
                    value=QuizQuestion(
                        question_id="q1",
                        topic=call.arguments["topic"],
                        prompt="Fallback quiz.",
                        expected_points=["fallback"],
                    ),
                )
            raise AssertionError(f"Unexpected tool call: {call.name}")

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        evidence_snapshots=[
            EvidenceSnapshot(
                chunk_id="old-chunk",
                summary="Stale evidence from a previous turn.",
            )
        ],
    )

    state = MultiAgentOrchestrator(registry=FakeRegistry()).run_turn(state)

    quiz_call = calls[1]
    assert state.status == "waiting_for_answer"
    assert state.evidence_snapshots == []
    assert quiz_call.arguments["materials"] == []


def _scored_chunk(index: int):
    from final_agent.schemas import Chunk, ScoredChunk

    return ScoredChunk(
        chunk=Chunk(
            chunk_id=f"chunk-{index}",
            doc_id=f"doc-{index}",
            text=f"Full text for chunk {index}.",
            heading_path=["Week 1", f"Topic {index}"],
            page_num=index + 1,
            metadata={"source_path": f"slides/week-{index}.pdf"},
        ),
        score=1.0 - (index / 10),
        source="rrf",
    )
