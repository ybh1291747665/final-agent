from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar


T = TypeVar("T")


class TokenBudgeter:
    """Token-aware text budgeting with a safe fallback for offline test runs."""

    def __init__(self, model: str = "cl100k_base"):
        self.model = model
        self._encoding = self._load_encoding(model)

    def _load_encoding(self, model: str):
        try:
            import tiktoken

            try:
                return tiktoken.encoding_for_model(model)
            except KeyError:
                return tiktoken.get_encoding("cl100k_base")
        except ModuleNotFoundError:
            return None

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        # Conservative fallback: CJK tends toward one token per char; ASCII words are cheaper.
        return max(1, len(text.encode("utf-8")) // 3)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0 or not text:
            return ""
        if self.count_tokens(text) <= max_tokens:
            return text
        if self._encoding is not None:
            tokens = self._encoding.encode(text)
            return self._encoding.decode(tokens[:max_tokens]).rstrip()

        result: list[str] = []
        used = 0
        for char in text:
            cost = self.count_tokens(char)
            if used + cost > max_tokens:
                break
            result.append(char)
            used += cost
        return "".join(result).rstrip()

    def fit_items_to_budget(
        self,
        items: Sequence[T],
        max_tokens: int,
        text_of: Callable[[T], str],
    ) -> list[T]:
        if max_tokens <= 0:
            return []
        selected: list[T] = []
        used = 0
        for item in items:
            cost = self.count_tokens(text_of(item))
            if selected and used + cost > max_tokens:
                break
            if not selected and cost > max_tokens:
                selected.append(item)
                break
            selected.append(item)
            used += cost
        return selected
