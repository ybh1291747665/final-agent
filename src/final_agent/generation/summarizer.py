"""Document summarizer — traverse chunks by page or in full for structured summaries.

Unlike the QA path (semantic search → top-k chunks), this module walks through
ALL chunks of a document in order, batching them into LLM calls that fit the
context window.
"""

from __future__ import annotations

import logging
from pathlib import Path

from final_agent.generation.llm_client import generate as llm_generate
from final_agent.generation.prompts import (
    PAGE_BY_PAGE_PROMPT,
    FULL_SUMMARY_PROMPT,
    KEY_POINTS_PROMPT,
)
from final_agent.knowledge.vector_store import get_chunks_by_doc as chroma_get_doc
from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

# Conservative estimate: ~2 chars per token for Chinese
_CHARS_PER_TOKEN = 2
# Reserve tokens for prompt overhead and LLM output
_PROMPT_OVERHEAD = 500


def summarize_document(
    doc_id: str,
    mode: str,
    settings: Settings | None = None,
    *,
    max_chunks_per_batch: int = 20,
    temperature: float = 0.3,
) -> str:
    """Walk through all chunks of *doc_id* and produce a structured summary.

    Args:
        doc_id: Document identifier.
        mode: One of ``"page_by_page"``, ``"full_summary"``, ``"key_points"``.
        settings: Application settings.
        max_chunks_per_batch: Chunks per LLM call (controls context window).
        temperature: LLM temperature for summary generation.

    Returns:
        Concatenated summary text.
    """
    if settings is None:
        settings = load_settings()

    # Get all chunks for this document
    all_chunks = chroma_get_doc(doc_id, settings=settings)
    if not all_chunks:
        return f"(文档 {doc_id} 没有内容)"

    if mode == "page_by_page":
        return _summarize_by_page(all_chunks, settings, max_chunks_per_batch, temperature)
    elif mode == "full_summary":
        return _summarize_full(all_chunks, settings, max_chunks_per_batch, temperature, FULL_SUMMARY_PROMPT)
    elif mode == "key_points":
        return _summarize_full(all_chunks, settings, max_chunks_per_batch, temperature, KEY_POINTS_PROMPT)
    else:
        raise ValueError(f"Unknown summary mode: {mode}. Use page_by_page, full_summary, or key_points.")


def _batch_chunks(chunks: list[Chunk], max_chunks: int, max_tokens: int) -> list[list[Chunk]]:
    """Group chunks into batches that fit within *max_tokens*."""
    batches: list[list[Chunk]] = []
    current: list[Chunk] = []
    current_chars = 0
    char_limit = (max_tokens - _PROMPT_OVERHEAD) * _CHARS_PER_TOKEN

    for ch in chunks:
        ch_len = len(ch.text)
        if current and (len(current) >= max_chunks or current_chars + ch_len > char_limit):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(ch)
        current_chars += ch_len

    if current:
        batches.append(current)
    return batches


def _summarize_by_page(
    chunks: list[Chunk],
    settings: Settings,
    max_chunks_per_batch: int,
    temperature: float,
) -> str:
    """Group chunks by page_num and summarize each page."""
    # Group by page_num
    pages: dict[int, list[Chunk]] = {}
    for ch in chunks:
        pn = ch.page_num or 1
        pages.setdefault(pn, []).append(ch)

    parts: list[str] = []
    for pn in sorted(pages):
        page_chunks = pages[pn]
        # Sort within page by char_start
        page_chunks.sort(key=lambda c: c.char_start)
        chunk_text = "\n\n".join(c.text for c in page_chunks)
        prompt = PAGE_BY_PAGE_PROMPT.format(page=pn, chunks=chunk_text)

        logger.info("Summarizing page %d/%d ...", pn, max(pages))
        try:
            raw = llm_generate(
                [{"role": "user", "content": prompt}],
                settings=settings,
                temperature=temperature,
            )
            parts.append(f"## 第 {pn} 页\n\n{raw}")
        except Exception as e:
            logger.error("Page %d summary failed: %s", pn, e)
            parts.append(f"## 第 {pn} 页\n\n> ⚠️ 总结失败: {e}")

    return "\n\n---\n\n".join(parts)


def _summarize_full(
    chunks: list[Chunk],
    settings: Settings,
    max_chunks_per_batch: int,
    temperature: float,
    prompt_template: str,
) -> str:
    """Batch all chunks (sorted by char_start) and call LLM for each batch."""
    chunks_sorted = sorted(chunks, key=lambda c: c.char_start)
    max_tokens = settings.models_llm.max_tokens
    batches = _batch_chunks(chunks_sorted, max_chunks_per_batch, max_tokens)

    parts: list[str] = []
    for i, batch in enumerate(batches):
        chunk_text = "\n\n".join(
            f"[{c.chunk_id}] {c.text}" for c in batch
        )
        prompt = prompt_template.format(chunks=chunk_text)

        logger.info("Summary batch %d/%d (%d chunks) ...", i + 1, len(batches), len(batch))
        try:
            raw = llm_generate(
                [{"role": "user", "content": prompt}],
                settings=settings,
                temperature=temperature,
            )
            parts.append(raw)
        except Exception as e:
            logger.error("Summary batch %d failed: %s", i + 1, e)
            parts.append(f"> ⚠️ 批次 {i + 1} 总结失败: {e}")

    return "\n\n".join(parts)
