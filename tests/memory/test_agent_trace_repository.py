from __future__ import annotations


def test_repository_persists_agent_trace(tmp_path):
    from final_agent.agent.models import AgentToolTraceEntry
    from final_agent.agent.roles import AgentRole
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "memory.sqlite")

    repo.append_agent_trace(
        "s1",
        AgentToolTraceEntry(
            agent_role=AgentRole.RETRIEVAL,
            tool_name="search_course_material",
            input_summary="review CI",
            output_summary="2 chunks",
            ok=True,
            elapsed_ms=3,
            fallback_reason="",
        ),
    )

    trace = repo.list_agent_trace("s1")

    assert len(trace) == 1
    assert trace[0].sequence_no == 1
    assert trace[0].agent_role == AgentRole.RETRIEVAL
    assert trace[0].tool_name == "search_course_material"
    assert trace[0].output_summary == "2 chunks"
