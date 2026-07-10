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


def test_repository_upserts_and_filters_memory_items(tmp_path):
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    repo.upsert_memory_item(
        scope="session",
        scope_id="s1",
        kind="session_summary",
        content="reviewed CI",
        token_count=3,
        metadata={"turn": 1},
    )
    repo.upsert_memory_item(
        scope="session",
        scope_id="s1",
        kind="session_summary",
        content="reviewed CI and branching",
        token_count=5,
        metadata={"turn": 2},
    )
    repo.upsert_memory_item(
        scope="topic",
        scope_id="CI",
        kind="topic_memory",
        content="needs tests",
        token_count=2,
    )

    session_items = repo.list_memory_items(scope="session", scope_id="s1", kind="session_summary")
    topic_items = repo.list_memory_items(scope="topic", kind="topic_memory")

    assert len(session_items) == 1
    assert session_items[0]["content"] == "reviewed CI and branching"
    assert session_items[0]["metadata"] == {"turn": 2}
    assert topic_items[0]["content"] == "needs tests"
