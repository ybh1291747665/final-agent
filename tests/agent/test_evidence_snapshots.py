from __future__ import annotations


def test_agent_state_carries_compact_evidence_snapshots():
    from final_agent.agent.models import AgentState, EvidenceSnapshot

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        evidence_snapshots=[
            EvidenceSnapshot(
                chunk_id="aaaabbbb1111",
                doc_id="doc-a",
                source_path="E:/courses/software-engineering.pdf",
                page_num=12,
                heading="Continuous Integration",
                summary="CI runs automated builds and tests.",
                score=0.91,
                retrieval_source="rrf",
            )
        ],
    )

    assert state.evidence_snapshots[0].chunk_id == "aaaabbbb1111"
    assert state.evidence_snapshots[0].page_num == 12
    assert state.evidence_snapshots[0].summary == "CI runs automated builds and tests."


def test_evidence_snapshot_does_not_require_full_chunk_text():
    from final_agent.agent.models import EvidenceSnapshot

    snapshot = EvidenceSnapshot(
        chunk_id="aaaabbbb1111",
        doc_id="doc-a",
        source_path="E:/courses/software-engineering.pdf",
        page_num=12,
        heading="Continuous Integration",
        summary="CI runs automated builds and tests.",
        score=0.91,
        retrieval_source="rrf",
    )

    assert "text" not in snapshot.model_dump()
