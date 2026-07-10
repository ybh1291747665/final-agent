from __future__ import annotations

import re

from final_agent.agent.models import AnswerQualityReport, CriticWarning, EvidenceSnapshot


_CITATION_RE = re.compile(r"\[([A-Za-z0-9_-]{3,64})\]")
_SENTENCE_RE = re.compile(r"[^。！？.!?\n]+[。！？.!?]?")


def verify_evidence(*, quiz_prompt: str, evidence_count: int) -> list[CriticWarning]:
    if quiz_prompt and evidence_count <= 0:
        return [
            CriticWarning(
                code="missing_evidence",
                message="Quiz was generated without retrieved course evidence.",
            )
        ]
    return []


def evaluate_answer_quality(answer: str, evidence: list[EvidenceSnapshot]) -> AnswerQualityReport:
    evidence_ids = {snapshot.chunk_id for snapshot in evidence}
    citations = _CITATION_RE.findall(answer)
    unsupported = [citation for citation in citations if citation not in evidence_ids]
    missing_citation_count = 0
    for sentence in _SENTENCE_RE.findall(answer):
        text = sentence.strip()
        if not text:
            continue
        # Headings, list markers, and explicit uncertainty statements are not factual claims.
        if len(text) <= 8 or text.endswith(":") or text.endswith("：") or "不确定" in text:
            continue
        if not _CITATION_RE.search(text):
            missing_citation_count += 1

    warnings: list[str] = []
    if evidence and not citations:
        warnings.append("answer_has_no_citations")
    if unsupported:
        warnings.append("answer_cites_unknown_evidence")
    if missing_citation_count:
        warnings.append("answer_has_uncited_claims")

    return AnswerQualityReport(
        citation_count=len(citations),
        missing_citation_count=missing_citation_count,
        unsupported_citation_count=len(unsupported),
        evidence_count=len(evidence),
        needs_revision=bool(warnings),
        warnings=warnings,
    )


def verify_answer_quality(*, answer: str, evidence: list[EvidenceSnapshot]) -> list[CriticWarning]:
    report = evaluate_answer_quality(answer, evidence)
    warnings: list[CriticWarning] = []
    for code in report.warnings:
        warnings.append(
            CriticWarning(
                code=code,
                message=_quality_warning_message(code),
            )
        )
    return warnings


def _quality_warning_message(code: str) -> str:
    messages = {
        "answer_has_no_citations": "Answer used evidence but did not cite it.",
        "answer_cites_unknown_evidence": "Answer cited chunks outside the selected evidence packet.",
        "answer_has_uncited_claims": "Answer contains factual-looking claims without citations.",
    }
    return messages.get(code, code)


def verify_grade_consistency(*, score: float, next_action: str) -> list[CriticWarning]:
    if score < 0.4 and next_action != "re_explain":
        return [
            CriticWarning(
                code="next_action_score_mismatch",
                message="Low score should usually lead to re_explain.",
            )
        ]
    if score > 0.7 and next_action != "advance_topic":
        return [
            CriticWarning(
                code="next_action_score_mismatch",
                message="High score should usually lead to advance_topic.",
            )
        ]
    return []
