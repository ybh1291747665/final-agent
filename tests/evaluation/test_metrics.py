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
        EvaluationResult(
            case_id="a",
            completed=True,
            expected_tools=["search"],
            actual_tools=["search"],
            required_citations=["c1"],
            retrieved_citations=["c1", "c3"],
            actual_citations=["c1", "c4"],
            expected_score_band="high",
            actual_score=0.8,
            elapsed_ms=100,
        ),
        EvaluationResult(
            case_id="b",
            completed=False,
            expected_tools=["quiz"],
            actual_tools=["search"],
            required_citations=["c2"],
            retrieved_citations=[],
            actual_citations=[],
            expected_score_band="low",
            actual_score=0.9,
            elapsed_ms=300,
            error="failed",
        ),
    ]

    summary = summarize_results(results)

    assert summary.total_cases == 2
    assert summary.task_completion_rate == 0.5
    assert summary.tool_selection_accuracy == 0.5
    assert summary.citation_grounding_rate == 0.5
    assert summary.retrieval_recall_at_5 == 0.5
    assert summary.evidence_recall_at_3 == 0.5
    assert summary.citation_precision == 0.5
    assert summary.grading_agreement == 0.5
    assert summary.mean_latency_ms == 200
    assert summary.error_rate == 0.5


def test_agent_final_runner_uses_agent_workflow(tmp_path):
    from final_agent.evaluation.runner import run_suite

    report = run_suite("agent-final", data_dir=tmp_path)
    first_tool_case = next(result for result in report["results"] if result["case_id"] == "tool-01")

    assert first_tool_case["actual_tools"] == ["search_course_material", "generate_quiz"]
    assert first_tool_case["completed"] is True
    assert first_tool_case["error"] == ""


def test_load_local_rag_cases_from_markdown(tmp_path):
    from final_agent.evaluation.dataset import load_local_rag_cases

    markdown_dir = tmp_path / "markdown" / "course-a"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "lesson.md").write_text(
        "<!-- page_start: 1 -->\n## Continuous Integration\n"
        "Continuous integration runs automated tests on every version control change.\n"
        "Pipelines make feedback faster and safer for teams.\n",
        encoding="utf-8",
    )

    cases = load_local_rag_cases(tmp_path, target_count=3)

    assert len(cases) == 3
    assert cases[0].case_id.startswith("local-retrieval-")
    assert cases[0].required_citations[0].startswith("course-a-")
    assert "Continuous Integration" in cases[0].user_input


def test_local_rag_cases_disambiguate_repeated_headings(tmp_path):
    from final_agent.evaluation.dataset import load_local_rag_cases

    markdown_dir = tmp_path / "markdown" / "course-a"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "lesson.md").write_text(
        "## Workflow\n"
        + "alpha deployment security automation " * 10
        + "\n## Workflow\n"
        + "beta threat modeling governance review " * 10,
        encoding="utf-8",
    )

    cases = load_local_rag_cases(tmp_path, target_count=2)

    assert len({case.user_input for case in cases}) == 2
    assert any("alpha" in case.user_input.lower() for case in cases)
    assert any("beta" in case.user_input.lower() for case in cases)


def test_agent_final_runner_uses_actual_local_citations(tmp_path):
    from final_agent.evaluation.runner import run_suite

    markdown_dir = tmp_path / "markdown" / "course-a"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "lesson.md").write_text(
        "## Secure Version Control\n"
        "Secure version control protects code history and supports review workflows.\n",
        encoding="utf-8",
    )

    report = run_suite("agent-final", data_dir=tmp_path)
    result = report["results"][0]

    assert result["required_citations"]
    assert result["actual_citations"]
    assert result["actual_citations"][0] == result["required_citations"][0]
    assert not result["actual_citations"][0].startswith("fixture-")
    assert result["completed"] is True


def test_agent_final_runner_records_the_agent_search_top_five(tmp_path):
    from final_agent.evaluation.runner import run_suite

    markdown_dir = tmp_path / "markdown" / "course-a"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "lesson.md").write_text(
        "## Secure Version Control\n"
        "Secure version control protects code history and supports review workflows.\n",
        encoding="utf-8",
    )

    report = run_suite("agent-final", data_dir=tmp_path)
    result = report["results"][0]

    assert result["retrieved_citations"]
    assert result["actual_citations"]
    assert result["actual_citations"] == result["retrieved_citations"][:3]
    assert result["error"] == ""
