from __future__ import annotations

from collections.abc import Sequence
import re

from final_agent.agent.models import ContextBudget, EvidencePacket, EvidenceSnapshot
from final_agent.schemas import ReadingContext, ScoredChunk
from final_agent.token_budget import TokenBudgeter


def _heading(chunk) -> str:
    return " > ".join(chunk.heading_path) if chunk.heading_path else ""


def _source_path(chunk) -> str:
    return str(chunk.metadata.get("source_path", "") or "")


def _summary(text: str, max_chars: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def query_fingerprint(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", query.lower())
    return " ".join(dict.fromkeys(tokens))


def build_evidence_snapshots(
    results: Sequence[ScoredChunk],
    limit: int = 3,
    *,
    max_summary_chars: int = 220,
    max_summary_tokens: int | None = None,
    budgeter: TokenBudgeter | None = None,
) -> list[EvidenceSnapshot]:
    token_budgeter = budgeter or TokenBudgeter()
    snapshots: list[EvidenceSnapshot] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        summary = (
            token_budgeter.truncate_to_tokens(" ".join(chunk.text.split()), max_summary_tokens)
            if max_summary_tokens is not None
            else _summary(chunk.text, max_summary_chars)
        )
        if max_summary_tokens is not None and len(summary) > max_summary_chars:
            summary = _summary(summary, max_summary_chars)
        snapshots.append(
            EvidenceSnapshot(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                source_path=_source_path(chunk),
                page_num=chunk.page_num,
                heading=_heading(chunk),
                summary=summary,
                score=result.score,
                retrieval_source=result.source,
            )
        )
    return snapshots


def build_transient_materials(
    results: Sequence[ScoredChunk],
    limit: int = 3,
    *,
    max_material_chars: int | None = None,
    max_material_tokens: int | None = None,
    budgeter: TokenBudgeter | None = None,
) -> list[dict]:
    token_budgeter = budgeter or TokenBudgeter()
    materials: list[dict] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        if max_material_tokens is not None:
            text = token_budgeter.truncate_to_tokens(chunk.text, max_material_tokens)
            if max_material_chars is not None and len(text) > max_material_chars:
                text = _summary(text, max_material_chars)
        elif max_material_chars is not None:
            text = _summary(chunk.text, max_material_chars)
        else:
            text = chunk.text
        materials.append(
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "source_path": _source_path(chunk),
                "page_num": chunk.page_num,
                "heading": _heading(chunk),
                "text": text,
                "score": result.score,
                "retrieval_source": result.source,
            }
        )
    return materials


def build_evidence_packet(
    query: str,
    results: Sequence[ScoredChunk],
    *,
    course_ids: list[str] | None = None,
    reading_context: ReadingContext | None = None,
    created_turn: int = 0,
    budget: ContextBudget | None = None,
    budgeter: TokenBudgeter | None = None,
) -> EvidencePacket:
    selected_budget = budget or ContextBudget()
    token_budgeter = budgeter or TokenBudgeter()
    retrieved = [result.chunk.chunk_id for result in list(results)[:5]]
    snapshots = build_evidence_snapshots(
        results,
        limit=selected_budget.max_evidence_items,
        max_summary_chars=selected_budget.max_summary_chars,
        max_summary_tokens=selected_budget.max_evidence_tokens,
        budgeter=token_budgeter,
    )
    return EvidencePacket(
        query=query,
        course_ids=course_ids or [],
        reading_context=reading_context,
        retrieved_chunk_ids=retrieved,
        evidence_snapshots=snapshots,
        query_fingerprint=query_fingerprint(query),
        created_turn=created_turn,
        budget=selected_budget,
    )


def build_budgeted_transient_materials(
    results: Sequence[ScoredChunk],
    *,
    budget: ContextBudget | None = None,
    budgeter: TokenBudgeter | None = None,
) -> list[dict]:
    selected_budget = budget or ContextBudget()
    return build_transient_materials(
        results,
        limit=selected_budget.max_evidence_items,
        max_material_chars=selected_budget.max_material_chars,
        max_material_tokens=selected_budget.max_material_tokens,
        budgeter=budgeter,
    )


def summarize_evidence_for_trace(snapshots: Sequence[EvidenceSnapshot]) -> str:
    if not snapshots:
        return "0 evidence snapshots"
    return f"{len(snapshots)} evidence snapshots"
