from __future__ import annotations


def test_evaluation_metrics_handle_empty_results():
    from final_agent.evaluation.metrics import summarize_results

    summary = summarize_results([])

    assert summary.total_cases == 0
    assert summary.task_completion_rate == 0.0
    assert summary.error_rate == 0.0


def test_evaluation_metrics_calculate_rates():
    from final_agent.evaluation.metrics import summarize_results
    from final_agent.evaluation.models import EvaluationResult

    results = [
        EvaluationResult(case_id="a", completed=True, expected_tools=["search"], actual_tools=["search"], required_citations=["c1"], actual_citations=["c1"], expected_score_band="high", actual_score=0.8, elapsed_ms=100),
        EvaluationResult(case_id="b", completed=False, expected_tools=["quiz"], actual_tools=["search"], required_citations=["c2"], actual_citations=[], expected_score_band="low", actual_score=0.9, elapsed_ms=300, error="failed"),
    ]

    summary = summarize_results(results)

    assert summary.total_cases == 2
    assert summary.task_completion_rate == 0.5
    assert summary.tool_selection_accuracy == 0.5
    assert summary.citation_grounding_rate == 0.5
    assert summary.grading_agreement == 0.5
    assert summary.mean_latency_ms == 200
    assert summary.error_rate == 0.5


def test_agent_final_runner_uses_agent_workflow():
    from final_agent.evaluation.runner import run_suite

    report = run_suite("agent-final")
    first_tool_case = next(result for result in report["results"] if result["case_id"] == "tool-01")

    assert first_tool_case["actual_tools"] == ["search_course_material", "generate_quiz"]
