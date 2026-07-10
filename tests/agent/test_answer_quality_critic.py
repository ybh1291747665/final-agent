from __future__ import annotations


def test_answer_quality_report_flags_uncited_claims_and_unknown_citations():
    from final_agent.agent.critics import evaluate_answer_quality
    from final_agent.agent.models import EvidenceSnapshot

    report = evaluate_answer_quality(
        "CI runs tests [chunk-a]. It also deploys automatically [chunk-z]. This is another claim.",
        [EvidenceSnapshot(chunk_id="chunk-a", summary="CI runs tests.")],
    )

    assert report.citation_count == 2
    assert report.unsupported_citation_count == 1
    assert report.missing_citation_count == 1
    assert report.needs_revision is True
    assert "answer_cites_unknown_evidence" in report.warnings
    assert "answer_has_uncited_claims" in report.warnings


def test_answer_quality_report_accepts_fully_cited_answer():
    from final_agent.agent.critics import evaluate_answer_quality
    from final_agent.agent.models import EvidenceSnapshot

    report = evaluate_answer_quality(
        "CI runs automated builds [chunk-a].",
        [EvidenceSnapshot(chunk_id="chunk-a", summary="CI runs automated builds.")],
    )

    assert report.needs_revision is False
    assert report.warnings == []


def test_verify_answer_quality_returns_critic_warnings():
    from final_agent.agent.critics import verify_answer_quality
    from final_agent.agent.models import EvidenceSnapshot

    warnings = verify_answer_quality(
        answer="CI runs automated builds.",
        evidence=[EvidenceSnapshot(chunk_id="chunk-a", summary="CI runs automated builds.")],
    )

    assert [warning.code for warning in warnings] == [
        "answer_has_no_citations",
        "answer_has_uncited_claims",
    ]
