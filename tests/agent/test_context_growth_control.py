from __future__ import annotations


def test_orchestrator_reuses_evidence_packet_for_similar_followup(monkeypatch):
    from final_agent.agent.evidence import build_evidence_packet
    from final_agent.agent.models import AgentState, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.schemas import Chunk, ScoredChunk

    search_calls = []

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            if call.name == "search_course_material":
                search_calls.append(call)
                return ToolResult(ok=True, value=[_scored_chunk()])
            if call.name == "generate_quiz":
                return ToolResult(
                    ok=True,
                    value=QuizQuestion(
                        question_id="q1",
                        topic=call.arguments["topic"],
                        prompt="Explain CI.",
                        expected_points=["automation"],
                    ),
                )
            raise AssertionError(call.name)

    packet = build_evidence_packet(
        "review continuous integration",
        [ScoredChunk(chunk=Chunk(chunk_id="chunk-a", doc_id="doc-a", text="Full CI text."), score=1, source="rrf")],
        course_ids=["course-a"],
        created_turn=1,
    )
    state = AgentState(
        session_id="s1",
        learning_goal="continuous integration review",
        course_ids=["course-a"],
        evidence_packet=packet,
        evidence_snapshots=packet.evidence_snapshots,
        turn_index=2,
    )

    monkeypatch.setattr(
        "final_agent.knowledge.vector_store.get_chunks_by_ids",
        lambda chunk_ids, course_ids=None, settings=None: [
            Chunk(chunk_id="chunk-a", doc_id="doc-a", text="Full CI text.")
        ],
    )

    updated = MultiAgentOrchestrator(registry=FakeRegistry()).run_turn(state)

    assert search_calls == []
    assert updated.retrieval_decision == "reused_evidence_packet"
    assert updated.status == "waiting_for_answer"


def test_orchestrator_resolves_memory_into_bounded_quiz_materials(tmp_path):
    from final_agent.agent.models import AgentState, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.memory.repository import MemoryRepository

    captured_materials = []

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            if call.name == "search_course_material":
                return ToolResult(ok=True, value=[_scored_chunk()])
            if call.name == "generate_quiz":
                captured_materials.extend(call.arguments["materials"])
                return ToolResult(
                    ok=True,
                    value=QuizQuestion(
                        question_id="q1",
                        topic=call.arguments["topic"],
                        prompt="Explain CI.",
                        expected_points=["automation"],
                    ),
                )
            raise AssertionError(call.name)

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    repo.upsert_memory_item(
        scope="session",
        scope_id="s1",
        kind="session_summary",
        content="Earlier turn: learner confused CI with deployment.",
    )

    updated = MultiAgentOrchestrator(repository=repo, registry=FakeRegistry()).run_turn(
        AgentState(session_id="s1", learning_goal="review CI", course_ids=["course-a"])
    )

    assert updated.status == "waiting_for_answer"
    assert any(material["retrieval_source"] == "memory" for material in captured_materials)
    assert "Earlier turn" in captured_materials[-1]["text"]


def test_agent_trace_summarizes_material_inputs_without_full_chunk_text():
    from final_agent.agent.models import AgentState, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.schemas import Chunk, ScoredChunk

    secret_text = "SECRET_FULL_CHUNK_TEXT " * 40

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            if call.name == "search_course_material":
                return ToolResult(
                    ok=True,
                    value=[
                        ScoredChunk(
                            chunk=Chunk(chunk_id="chunk-a", doc_id="doc-a", text=secret_text),
                            score=1.0,
                            source="rrf",
                        )
                    ],
                )
            if call.name == "generate_quiz":
                return ToolResult(
                    ok=True,
                    value=QuizQuestion(
                        question_id="q1",
                        topic=call.arguments["topic"],
                        prompt="Explain CI.",
                        expected_points=["automation"],
                    ),
                )
            raise AssertionError(call.name)

    updated = MultiAgentOrchestrator(registry=FakeRegistry()).run_turn(
        AgentState(session_id="s1", learning_goal="review CI", course_ids=["course-a"])
    )

    generate_trace = next(trace for trace in updated.agent_trace if trace.tool_name == "generate_quiz")

    assert generate_trace.input_summary.endswith("'materials': '1 materials'}")
    assert "SECRET_FULL_CHUNK_TEXT" not in generate_trace.input_summary


def test_completed_turn_updates_summary_and_state_avoids_full_chunk_growth(tmp_path):
    from final_agent.agent.models import AgentState, EvidenceSnapshot, GradeResult, QuizQuestion, ToolResult
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.memory.repository import MemoryRepository

    class FakeRegistry:
        def execute(self, role, call, *, allowed_tools):
            if call.name == "grade_answer":
                return ToolResult(ok=True, value=GradeResult(score=0.5, feedback="Review tests."))
            if call.name == "update_mastery":
                return ToolResult(ok=True, value=None)
            if call.name in {"verify_evidence", "verify_grade_consistency", "verify_answer_quality"}:
                return ToolResult(ok=True, value=[])
            raise AssertionError(call.name)

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        quiz=QuizQuestion(question_id="q1", topic="CI", prompt="Explain CI.", expected_points=["tests"]),
        learner_answer="CI runs tests.",
        grade=None,
        status="waiting_for_answer",
        evidence_snapshots=[
            EvidenceSnapshot(
                chunk_id="chunk-a",
                summary="compact summary",
            )
        ],
    )
    repo.create_session(state)

    updated = MultiAgentOrchestrator(repository=repo, registry=FakeRegistry()).run_turn(state)
    repo.save_session(updated)
    saved = repo.get_session("s1")

    assert saved.session_summary
    assert saved.turn_index == 1
    assert "very long full chunk text" not in saved.model_dump_json()
    assert repo.list_memory_items(scope="session", scope_id="s1", kind="session_summary")


def _scored_chunk():
    from final_agent.schemas import Chunk, ScoredChunk

    return ScoredChunk(
        chunk=Chunk(chunk_id="chunk-a", doc_id="doc-a", text="Full CI text."),
        score=1.0,
        source="rrf",
    )
