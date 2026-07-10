from __future__ import annotations


def test_llm_judge_parses_relevance_score(monkeypatch):
    from final_agent.evaluation import judge

    monkeypatch.setattr(
        judge,
        "llm_generate",
        lambda *args, **kwargs: '{"score": 0.85, "reason": "Evidence answers the learning goal."}',
    )

    result = judge.judge_evidence_relevance(
        "Explain continuous integration",
        ["Automated tests run on every commit."],
    )

    assert result == {
        "score": 0.85,
        "reason": "Evidence answers the learning goal.",
    }


def test_llm_judge_handles_invalid_output(monkeypatch):
    from final_agent.evaluation import judge

    monkeypatch.setattr(judge, "llm_generate", lambda *args, **kwargs: "not-json")

    result = judge.judge_evidence_relevance("question", ["evidence"])

    assert result["score"] is None
    assert "invalid" in result["reason"].lower()
