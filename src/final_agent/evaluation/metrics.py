from __future__ import annotations

from final_agent.evaluation.models import EvaluationResult, EvaluationSummary


def _score_matches_band(score: float | None, band: str | None) -> bool:
    if band is None or score is None:
        return False
    if band == "low":
        return score < 0.4
    if band == "medium":
        return 0.4 <= score <= 0.7
    if band == "high":
        return score > 0.7
    return False


def summarize_results(results: list[EvaluationResult]) -> EvaluationSummary:
    total = len(results)
    if total == 0:
        return EvaluationSummary()

    completed = sum(1 for result in results if result.completed)
    exact_tools = sum(1 for result in results if result.actual_tools == result.expected_tools)
    required_citations = sum(len(result.required_citations) for result in results)
    matched_citations = sum(
        len(set(result.required_citations).intersection(result.actual_citations))
        for result in results
    )
    gradable = [result for result in results if result.expected_score_band is not None]
    grading_matches = sum(
        1 for result in gradable if _score_matches_band(result.actual_score, result.expected_score_band)
    )
    latencies = sorted(result.elapsed_ms for result in results)
    p95_index = min(len(latencies) - 1, int(len(latencies) * 0.95))

    return EvaluationSummary(
        total_cases=total,
        task_completion_rate=completed / total,
        tool_selection_accuracy=exact_tools / total,
        citation_grounding_rate=(matched_citations / required_citations) if required_citations else 0.0,
        grading_agreement=(grading_matches / len(gradable)) if gradable else 0.0,
        mean_latency_ms=int(sum(latencies) / total),
        p95_latency_ms=latencies[p95_index],
        error_rate=sum(1 for result in results if result.error) / total,
    )
