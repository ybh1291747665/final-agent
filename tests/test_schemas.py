from __future__ import annotations


def test_existing_schema_models_round_trip():
    from final_agent.schemas import Chunk, GeneratedAnswer, HallucinationFlag, ScoredChunk, VerifiedAnswer

    chunk = Chunk(chunk_id="abc12345", doc_id="doc", course_id="course", text="text", heading_path=["A"], page_num=3)
    scored = ScoredChunk(chunk=chunk, score=0.8, source="rrf")
    answer = GeneratedAnswer(answer="Use automation [abc12345]", citations=["abc12345"], model="fake")
    verified = VerifiedAnswer(raw_answer=answer.answer, flags=[HallucinationFlag(sentence="Use automation", cited_chunk_id="abc12345", similarity_score=0.9, flagged=False)])

    assert Chunk.model_validate_json(chunk.model_dump_json()).page_num == 3
    assert ScoredChunk.model_validate_json(scored.model_dump_json()).chunk.chunk_id == "abc12345"
    assert GeneratedAnswer.model_validate_json(answer.model_dump_json()).citations == ["abc12345"]
    restored = VerifiedAnswer.model_validate_json(verified.model_dump_json())
    assert restored.flags[0].similarity_score == 0.9
    assert restored.is_clean is True
