from __future__ import annotations

from final_agent.agent.models import ContextBudget
from final_agent.token_budget import TokenBudgeter


class MemoryResolver:
    def __init__(self, repository, budgeter: TokenBudgeter | None = None):
        self.repository = repository
        self.budgeter = budgeter or TokenBudgeter()

    def resolve(
        self,
        *,
        session_id: str,
        topic: str = "",
        course_ids: list[str] | None = None,
        budget: ContextBudget | None = None,
    ) -> dict:
        selected_budget = budget or ContextBudget()
        candidates: list[dict] = []
        candidates.extend(
            self.repository.list_memory_items(
                scope="session",
                scope_id=session_id,
                kind="session_summary",
            )
        )
        if topic:
            candidates.extend(
                self.repository.list_memory_items(
                    scope="topic",
                    scope_id=topic,
                    kind="topic_memory",
                )
            )
        for course_id in course_ids or []:
            candidates.extend(
                self.repository.list_memory_items(
                    scope="course",
                    scope_id=course_id,
                    kind="course_memory",
                )
            )

        fitted = self.budgeter.fit_items_to_budget(
            candidates,
            selected_budget.max_history_tokens,
            lambda item: str(item.get("content", "")),
        )
        content = self.budgeter.truncate_to_tokens(
            "\n".join(str(item.get("content", "")) for item in fitted if item.get("content")),
            selected_budget.max_history_tokens,
        )
        return {
            "items": fitted,
            "content": content,
            "token_count": self.budgeter.count_tokens(content),
        }
