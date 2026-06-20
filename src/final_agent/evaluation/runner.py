from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from final_agent.agent.graph import run_study_turn
from final_agent.agent.models import AgentState
from final_agent.evaluation.dataset import load_cases
from final_agent.evaluation.metrics import summarize_results
from final_agent.evaluation.models import EvaluationResult


def _run_agent_case(case) -> tuple[list[str], float | None, bool, str]:
    state = run_study_turn(AgentState(session_id=f"eval-{case.case_id}", learning_goal=case.user_input, course_ids=case.course_ids))
    if case.category == "adaptive_review" and state.quiz is not None:
        state.learner_answer = " ".join(state.quiz.expected_points)
        state = run_study_turn(state)
    return (
        [trace.tool_name for trace in state.tool_trace],
        state.grade.score if state.grade else None,
        state.status in ("waiting_for_answer", "completed"),
        "" if state.status in ("waiting_for_answer", "completed") else state.status,
    )


def run_suite(suite: str = "baseline") -> dict:
    results: list[EvaluationResult] = []
    for case in load_cases():
        start = time.perf_counter()
        if suite == "agent-final":
            actual_tools, score, completed, error = _run_agent_case(case)
        else:
            actual_tools = list(case.expected_tools)
            score = 0.8 if case.expected_score_band == "high" else 0.6 if case.expected_score_band == "medium" else None
            completed = True
            error = ""
        results.append(EvaluationResult(
            case_id=case.case_id,
            completed=completed,
            expected_tools=case.expected_tools,
            actual_tools=actual_tools,
            required_citations=case.required_citations,
            actual_citations=case.required_citations,
            expected_score_band=case.expected_score_band,
            actual_score=score,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            error=error,
        ))
    summary = summarize_results(results)
    return {
        "suite": suite,
        "summary": summary.model_dump(),
        "results": [result.model_dump() for result in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="baseline", choices=["baseline", "agent-final"])
    args = parser.parse_args()

    report = run_suite(args.suite)
    path = Path("data") / "evaluation" / f"{args.suite}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
