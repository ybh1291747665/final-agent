from __future__ import annotations


def test_repository_persists_sessions_mastery_and_trace(tmp_path):
    from final_agent.agent.models import AgentState, ToolTraceEntry
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    state = AgentState(session_id="s1", learning_goal="review CI")

    repo.create_session(state)
    repo.upsert_mastery("s1", "CI", 0.5)
    repo.upsert_mastery("s1", "CI", 1.0)
    repo.append_trace("s1", ToolTraceEntry(tool_name="search_course_material", input_summary="CI", ok=True, elapsed_ms=2))

    assert repo.get_session("s1").learning_goal == "review CI"
    assert repo.get_mastery("s1")["CI"].score == 0.65
    assert repo.list_trace("s1")[0].sequence_no == 1


def test_repository_isolates_sessions(tmp_path):
    from final_agent.agent.models import AgentState
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    repo.create_session(AgentState(session_id="s1", learning_goal="one"))
    repo.create_session(AgentState(session_id="s2", learning_goal="two"))
    repo.upsert_mastery("s1", "CI", 1.0)

    assert repo.get_mastery("s2") == {}
