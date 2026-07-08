from __future__ import annotations

from collections.abc import Sequence

from final_agent.agent.models import EvidenceSnapshot
from final_agent.schemas import ScoredChunk


def _heading(chunk) -> str:
    return " > ".join(chunk.heading_path) if chunk.heading_path else ""


def _source_path(chunk) -> str:
    return str(chunk.metadata.get("source_path", "") or "")


def _summary(text: str, max_chars: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def build_evidence_snapshots(results: Sequence[ScoredChunk], *, limit: int = 3) -> list[EvidenceSnapshot]:
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
                summary=_summary(chunk.text),
                score=result.score,
                retrieval_source=result.source,
            )
        )
    return snapshots


def build_transient_materials(results: Sequence[ScoredChunk], *, limit: int = 3) -> list[dict]:
    materials: list[dict] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        materials.append(
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "source_path": _source_path(chunk),
                "page_num": chunk.page_num,
                "heading": _heading(chunk),
                "text": chunk.text,
                "score": result.score,
                "retrieval_source": result.source,
            }
        )
    return materials


def summarize_evidence_for_trace(snapshots: Sequence[EvidenceSnapshot]) -> str:
    if not snapshots:
        return "0 evidence snapshots"
    return f"{len(snapshots)} evidence snapshots"
