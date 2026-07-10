from __future__ import annotations

import json

from final_agent.generation.llm_client import generate as llm_generate
from final_agent.settings import Settings


def judge_evidence_relevance(
    query: str,
    evidence: list[str],
    settings: Settings | None = None,
) -> dict[str, float | str | None]:
    prompt = (
        "Judge whether the evidence is relevant to the learning goal. "
        'Return JSON only: {"score": 0.0-1.0, "reason": "brief reason"}.\n'
        f"Learning goal: {query}\nEvidence:\n" + "\n---\n".join(evidence)
    )
    raw = llm_generate(
        [
            {"role": "system", "content": "You are a strict RAG evidence evaluator."},
            {"role": "user", "content": prompt},
        ],
        settings=settings,
        temperature=0.0,
        max_tokens=200,
    )
    try:
        payload = json.loads(raw)
        score = float(payload["score"])
        reason = str(payload["reason"])
        if not 0.0 <= score <= 1.0:
            raise ValueError("score out of range")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {"score": None, "reason": "Invalid LLM judge response."}
    return {"score": score, "reason": reason}
