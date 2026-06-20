"""Answer generator — builds prompts from retrieved chunks, calls LLM, extracts citations."""

from __future__ import annotations

import re
import logging

from final_agent.generation.llm_client import generate as llm_generate
from final_agent.generation.prompts import SYSTEM_PROMPT, QA_PROMPT, REVIEW_PROMPT, EXAM_PROMPT, DEEP_QA_SYSTEM, DEEP_QA_PROMPT
from final_agent.schemas import ScoredChunk, GeneratedAnswer
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[([a-f0-9]{8,16})\]")


def _format_chunks(chunks: list[ScoredChunk]) -> str:
    lines: list[str] = []
    for sc in chunks:
        c = sc.chunk
        heading = " > ".join(c.heading_path) if c.heading_path else "(top-level)"
        lines.append(f"[{c.chunk_id}] ({heading}) {c.text}")
    return "\n\n".join(lines)


def answer_question(
    question: str,
    chunks: list[ScoredChunk],
    settings: Settings | None = None,
    *,
    model: str | None = None,
) -> GeneratedAnswer:
    """Generate a cited answer from retrieved chunks.

    Args:
        question: User question.
        chunks: Retrieved and reranked ScoredChunk list.
        settings: Application settings.
        model: Override model name (e.g. deepseek-v4-flash / deepseek-v4-pro).

    Returns:
        GeneratedAnswer with answer text and extracted citations.
    """
    if settings is None:
        settings = load_settings()

    chunk_text = _format_chunks(chunks)
    user_prompt = QA_PROMPT.format(question=question, chunks=chunk_text)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = llm_generate(messages, settings=settings, model=model)
    citations = _extract_citations(raw)

    return GeneratedAnswer(
        answer=raw,
        citations=citations,
        model=model or settings.models_llm.model,
    )


def generate_review(
    topic: str,
    chunks: list[ScoredChunk],
    settings: Settings | None = None,
) -> GeneratedAnswer:
    """Generate a structured review summary."""
    if settings is None:
        settings = load_settings()

    chunk_text = _format_chunks(chunks)
    user_prompt = REVIEW_PROMPT.format(topic=topic, chunks=chunk_text)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = llm_generate(messages, settings=settings)

    return GeneratedAnswer(
        answer=raw,
        citations=_extract_citations(raw),
        model=settings.models_llm.model,
    )


def generate_exam(
    chunks: list[ScoredChunk],
    settings: Settings | None = None,
) -> GeneratedAnswer:
    """Generate practice exam questions."""
    if settings is None:
        settings = load_settings()

    chunk_text = _format_chunks(chunks)
    user_prompt = EXAM_PROMPT.format(chunks=chunk_text)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = llm_generate(messages, settings=settings)

    return GeneratedAnswer(
        answer=raw,
        citations=_extract_citations(raw),
        model=settings.models_llm.model,
    )


def _extract_citations(text: str) -> list[str]:
    """Extract unique [chunk_id] references from text."""
    return list(dict.fromkeys(_CITATION_RE.findall(text)))


def answer_deep(
    question: str,
    chunks: list[ScoredChunk],
    settings: Settings | None = None,
    *,
    model: str | None = None,
) -> GeneratedAnswer:
    """Deep review QA — multi-document synthesis with broader context.

    Uses a system prompt that encourages cross-document comparison and
    comprehensive answers. Designed to pair with ``deep_search()``.

    Args:
        model: Override model name (e.g. deepseek-v4-flash / deepseek-v4-pro).
    """
    if settings is None:
        settings = load_settings()

    chunk_text = _format_chunks(chunks)
    user_prompt = DEEP_QA_PROMPT.format(question=question, chunks=chunk_text)

    messages = [
        {"role": "system", "content": DEEP_QA_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    raw = llm_generate(messages, settings=settings, model=model)
    citations = _extract_citations(raw)

    return GeneratedAnswer(
        answer=raw,
        citations=citations,
        model=model or settings.models_llm.model,
    )
