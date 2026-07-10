from __future__ import annotations


def test_evidence_reuse_policy_reuses_similar_query_same_scope():
    from final_agent.agent.evidence_reuse import EvidenceReusePolicy
    from final_agent.agent.models import EvidencePacket

    packet = EvidencePacket(
        query="review continuous integration",
        course_ids=["course-a"],
        retrieved_chunk_ids=["chunk-a"],
        created_turn=1,
    )

    decision = EvidenceReusePolicy().decide(
        query="continuous integration review",
        course_ids=["course-a"],
        reading_context=None,
        previous_packet=packet,
        quality_report=None,
        current_turn=2,
    )

    assert decision.reuse is True
    assert decision.trace_value == "reused_evidence_packet"


def test_evidence_reuse_policy_forces_retrieval_when_scope_or_quality_changes():
    from final_agent.agent.evidence_reuse import EvidenceReusePolicy
    from final_agent.agent.models import AnswerQualityReport, EvidencePacket

    packet = EvidencePacket(query="review CI", course_ids=["course-a"], retrieved_chunk_ids=["chunk-a"])
    policy = EvidenceReusePolicy()

    changed_scope = policy.decide(
        query="review CI",
        course_ids=["course-b"],
        reading_context=None,
        previous_packet=packet,
        quality_report=None,
        current_turn=0,
    )
    poor_quality = policy.decide(
        query="review CI",
        course_ids=["course-a"],
        reading_context=None,
        previous_packet=packet,
        quality_report=AnswerQualityReport(needs_revision=True),
        current_turn=0,
    )

    assert changed_scope.reuse is False
    assert changed_scope.reason == "course_scope_changed"
    assert poor_quality.reuse is False
    assert poor_quality.reason == "previous_quality_needs_revision"
