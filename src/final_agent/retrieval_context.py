from __future__ import annotations

from final_agent.schemas import Chunk, ReadingContext, ScoredChunk


INDEX_SCHEMA_VERSION = 2


def chunk_index_text(chunk: Chunk) -> str:
    parts: list[str] = []
    if chunk.heading_path:
        parts.append(" > ".join(chunk.heading_path))
    if chunk.page_num is not None:
        parts.append(f"Page {chunk.page_num}")
    parts.append(chunk.text)
    return "\n".join(parts)


def _page_prior(chunk: Chunk, context: ReadingContext) -> float:
    if not context.page_boost_enabled or not context.doc_id or context.page_num is None:
        return 0.0
    if chunk.doc_id != context.doc_id or chunk.page_num is None:
        return 0.0
    distance = abs(chunk.page_num - context.page_num)
    if distance == 0:
        return 0.15
    if distance == 1:
        return 0.08
    return 0.0


def apply_reading_context(
    results: list[ScoredChunk],
    context: ReadingContext | None,
) -> list[ScoredChunk]:
    if not results or context is None or not context.page_boost_enabled:
        return results

    scores = [result.score for result in results]
    low, high = min(scores), max(scores)
    spread = high - low

    def rank_value(result: ScoredChunk) -> float:
        relevance = (result.score - low) / spread if spread > 0 else 1.0
        return relevance + _page_prior(result.chunk, context)

    return sorted(results, key=rank_value, reverse=True)
