from __future__ import annotations

from copy import deepcopy

from final_agent.token_budget import TokenBudgeter


class ConversationCompressor:
    def __init__(
        self,
        *,
        max_messages: int = 8,
        max_history_tokens: int = 2000,
        keep_recent: int = 4,
        budgeter: TokenBudgeter | None = None,
    ):
        self.max_messages = max_messages
        self.max_history_tokens = max_history_tokens
        self.keep_recent = keep_recent
        self.budgeter = budgeter or TokenBudgeter()

    def compress(self, conversation: dict) -> dict:
        conv = deepcopy(conversation)
        history = list(conv.get("history", []))
        if not self._should_compress(history):
            conv["history"] = [self._sanitize_message(message) for message in history]
            return conv

        old_messages = history[:-self.keep_recent] if self.keep_recent else history
        recent_messages = history[-self.keep_recent:] if self.keep_recent else []
        summary = self._build_summary(conv.get("conversation_summary", ""), old_messages)
        conv["conversation_summary"] = self.budgeter.truncate_to_tokens(summary, self.max_history_tokens)
        conv["history"] = [self._sanitize_message(message) for message in recent_messages]
        return conv

    def _should_compress(self, history: list[dict]) -> bool:
        if len(history) > self.max_messages:
            return True
        return self.budgeter.count_tokens(self._history_text(history)) > self.max_history_tokens

    def _build_summary(self, previous_summary: str, messages: list[dict]) -> str:
        lines: list[str] = []
        if previous_summary:
            lines.append(previous_summary)
        for message in messages:
            role = message.get("role", "message")
            content = str(message.get("content", "")).strip()
            if content:
                lines.append(f"{role}: {self.budgeter.truncate_to_tokens(content, 120)}")
        return "\n".join(lines)

    def _history_text(self, history: list[dict]) -> str:
        return "\n".join(str(message.get("content", "")) for message in history)

    def _sanitize_message(self, message: dict) -> dict:
        sanitized = deepcopy(message)
        registry = sanitized.get("chunk_registry")
        if isinstance(registry, dict):
            compact_registry = {}
            for chunk_id, entry in registry.items():
                if not isinstance(entry, dict):
                    compact_registry[chunk_id] = entry
                    continue
                compact_registry[chunk_id] = {
                    key: entry.get(key, "")
                    for key in (
                        "doc_id",
                        "source_path",
                        "file_name",
                        "page_num",
                        "heading",
                        "source",
                        "score",
                        "citation_label",
                    )
                }
                compact_registry[chunk_id]["summary"] = self.budgeter.truncate_to_tokens(
                    str(entry.get("summary") or entry.get("text") or ""),
                    80,
                )
            sanitized["chunk_registry"] = compact_registry
        return sanitized


def compress_conversations(conversations: dict) -> dict:
    compressor = ConversationCompressor()
    return {conv_id: compressor.compress(conv) for conv_id, conv in conversations.items()}
