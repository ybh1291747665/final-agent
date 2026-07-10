from __future__ import annotations


def test_memory_resolver_combines_session_topic_and_course_memory(tmp_path):
    from final_agent.agent.models import ContextBudget
    from final_agent.memory.repository import MemoryRepository
    from final_agent.memory.resolver import MemoryResolver

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    repo.upsert_memory_item(scope="session", scope_id="s1", kind="session_summary", content="session notes")
    repo.upsert_memory_item(scope="topic", scope_id="CI", kind="topic_memory", content="topic notes")
    repo.upsert_memory_item(scope="course", scope_id="course-a", kind="course_memory", content="course notes")

    resolved = MemoryResolver(repo).resolve(
        session_id="s1",
        topic="CI",
        course_ids=["course-a"],
        budget=ContextBudget(max_history_tokens=200),
    )

    assert "session notes" in resolved["content"]
    assert "topic notes" in resolved["content"]
    assert "course notes" in resolved["content"]
    assert resolved["token_count"] <= 200


def test_memory_resolver_truncates_single_oversized_memory_item(tmp_path):
    from final_agent.agent.models import ContextBudget
    from final_agent.memory.repository import MemoryRepository
    from final_agent.memory.resolver import MemoryResolver
    from final_agent.token_budget import TokenBudgeter

    repo = MemoryRepository(tmp_path / "memory.sqlite")
    repo.upsert_memory_item(
        scope="session",
        scope_id="s1",
        kind="session_summary",
        content="history " * 500,
    )
    budgeter = TokenBudgeter()

    resolved = MemoryResolver(repo, budgeter).resolve(
        session_id="s1",
        budget=ContextBudget(max_history_tokens=200),
    )

    assert resolved["token_count"] <= 200
    assert budgeter.count_tokens(resolved["content"]) <= 200
