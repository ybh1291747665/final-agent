from __future__ import annotations

import re
from dataclasses import dataclass

from final_agent.agent.models import AnswerQualityReport, EvidencePacket
from final_agent.schemas import ReadingContext


@dataclass(frozen=True)
class EvidenceReuseDecision:
    reuse: bool
    reason: str

    @property
    def trace_value(self) -> str:
        return "reused_evidence_packet" if self.reuse else "retrieved"


class EvidenceReusePolicy:
    def __init__(self, *, min_query_similarity: float = 0.55, max_turn_age: int = 3):
        self.min_query_similarity = min_query_similarity
        self.max_turn_age = max_turn_age

    def decide(
        self,
        *,
        query: str,
        course_ids: list[str],
        reading_context: ReadingContext | None,
        previous_packet: EvidencePacket | None,
        quality_report: AnswerQualityReport | None,
        current_turn: int,
    ) -> EvidenceReuseDecision:
        if previous_packet is None:
            return EvidenceReuseDecision(False, "missing_packet")
        if sorted(previous_packet.course_ids) != sorted(course_ids or []):
            return EvidenceReuseDecision(False, "course_scope_changed")
        if _context_key(previous_packet.reading_context) != _context_key(reading_context):
            return EvidenceReuseDecision(False, "reading_context_changed")
        if quality_report and quality_report.needs_revision:
            return EvidenceReuseDecision(False, "previous_quality_needs_revision")
        if current_turn - previous_packet.created_turn > self.max_turn_age:
            return EvidenceReuseDecision(False, "packet_expired")
        similarity = _jaccard(_tokens(query), _tokens(previous_packet.query))
        if similarity < self.min_query_similarity:
            return EvidenceReuseDecision(False, "query_changed")
        return EvidenceReuseDecision(True, "similar_query")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text) if token.strip()}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left.intersection(right)) / len(left.union(right))


def _context_key(context: ReadingContext | None) -> tuple[str, int | None, bool]:
    if context is None:
        return ("", None, True)
    return (context.doc_id, context.page_num, context.page_boost_enabled)
