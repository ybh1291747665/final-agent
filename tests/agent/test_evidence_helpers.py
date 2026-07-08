from __future__ import annotations


def test_evidence_snapshots_keep_top_three_and_compact_fields():
    from final_agent.agent.evidence import build_evidence_snapshots
    from final_agent.schemas import Chunk, ScoredChunk

    results = [
        ScoredChunk(
            chunk=Chunk(
                chunk_id=f"chunk-{idx}",
                doc_id="doc-a",
                text=f"Evidence text {idx} " * 20,
                heading_path=["CI", f"Part {idx}"],
                page_num=idx,
                metadata={"source_path": "E:/courses/software-engineering.pdf"},
            ),
            score=1.0 - idx * 0.1,
            source="rrf",
        )
        for idx in range(1, 5)
    ]

    snapshots = build_evidence_snapshots(results, limit=3)

    assert [snapshot.chunk_id for snapshot in snapshots] == ["chunk-1", "chunk-2", "chunk-3"]
    assert snapshots[0].heading == "CI > Part 1"
    assert snapshots[0].source_path == "E:/courses/software-engineering.pdf"
    assert snapshots[0].page_num == 1
    assert len(snapshots[0].summary) <= 220
    assert "text" not in snapshots[0].model_dump()


def test_materials_keep_full_text_for_transient_tool_inputs():
    from final_agent.agent.evidence import build_transient_materials
    from final_agent.schemas import Chunk, ScoredChunk

    results = [
        ScoredChunk(
            chunk=Chunk(
                chunk_id="aaaabbbb1111",
                doc_id="doc-a",
                text="CI runs automated builds and tests.",
                heading_path=["CI"],
                page_num=7,
                metadata={"source_path": "E:/courses/software-engineering.pdf"},
            ),
            score=0.91,
            source="rrf",
        )
    ]

    materials = build_transient_materials(results, limit=3)

    assert materials == [
        {
            "chunk_id": "aaaabbbb1111",
            "doc_id": "doc-a",
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 7,
            "heading": "CI",
            "text": "CI runs automated builds and tests.",
            "score": 0.91,
            "retrieval_source": "rrf",
        }
    ]
