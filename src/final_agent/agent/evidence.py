from __future__ import annotations

from collections.abc import Sequence

from final_agent.agent.models import ContextBudget, EvidencePacket, EvidenceSnapshot
from final_agent.schemas import ScoredChunk


def _heading(chunk) -> str:
    return " > ".join(chunk.heading_path) if chunk.heading_path else ""


def _source_path(chunk) -> str:
    return str(chunk.metadata.get("source_path", "") or "")


def _summary(text: str, max_chars: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def build_evidence_snapshots(
    results: Sequence[ScoredChunk],
    limit: int = 3,
    *,
    max_summary_chars: int = 220,
) -> list[EvidenceSnapshot]:
    snapshots: list[EvidenceSnapshot] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        snapshots.append(
            EvidenceSnapshot(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                source_path=_source_path(chunk),
                page_num=chunk.page_num,
                heading=_heading(chunk),
                summary=_summary(chunk.text, max_summary_chars),
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
) -> list[dict]:
    materials: list[dict] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        text = chunk.text if max_material_chars is None else _summary(chunk.text, max_material_chars)
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
    budget: ContextBudget | None = None,
) -> EvidencePacket:
    selected_budget = budget or ContextBudget()
    retrieved = [result.chunk.chunk_id for result in list(results)[:5]]
    snapshots = build_evidence_snapshots(
        results,
        limit=selected_budget.max_evidence_items,
        max_summary_chars=selected_budget.max_summary_chars,
    )
    return EvidencePacket(
        query=query,
        retrieved_chunk_ids=retrieved,
        evidence_snapshots=snapshots,
        budget=selected_budget,
    )


def build_budgeted_transient_materials(
    results: Sequence[ScoredChunk],
    *,
    budget: ContextBudget | None = None,
) -> list[dict]:
    selected_budget = budget or ContextBudget()
    return build_transient_materials(
        results,
        limit=selected_budget.max_evidence_items,
        max_material_chars=selected_budget.max_material_chars,
    )


def summarize_evidence_for_trace(snapshots: Sequence[EvidenceSnapshot]) -> str:
    if not snapshots:
        return "0 evidence snapshots"
    return f"{len(snapshots)} evidence snapshots"
