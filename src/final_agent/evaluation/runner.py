from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import re
import time
from collections.abc import Iterator
from pathlib import Path

from final_agent.agent import graph as agent_graph
from final_agent.agent.models import AgentState, ToolResult
from final_agent.evaluation.dataset import load_cases, load_local_chunks, load_local_rag_cases
from final_agent.evaluation.metrics import summarize_results
from final_agent.evaluation.models import EvaluationResult
from final_agent.schemas import Chunk, ScoredChunk


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", value) if len(token) > 2}


def _score_local_chunks(query: str, chunks: list[Chunk], course_ids: list[str], top_k: int = 5) -> list[tuple[int, Chunk]]:
    query_tokens = _tokens(query)
    scored: list[tuple[int, Chunk]] = []
    for chunk in chunks:
        if course_ids and chunk.course_id not in course_ids:
            continue
        chunk_tokens = _tokens(" ".join(chunk.heading_path) + " " + chunk.text)
        score = len(query_tokens.intersection(chunk_tokens))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
    return scored[:top_k]


def _search_local_citations(query: str, chunks: list[Chunk], course_ids: list[str], top_k: int = 5) -> list[str]:
    return [chunk.chunk_id for _, chunk in _score_local_chunks(query, chunks, course_ids, top_k)]


@contextmanager
def _evaluation_search_adapter(chunks: list[Chunk]) -> Iterator[list[list[str]]]:
    original_search = agent_graph.search_course_material
    recorded_searches: list[list[str]] = []

    def _search(
        query: str,
        course_ids: list[str] | None = None,
        top_k: int = 5,
        reading_context=None,
    ) -> ToolResult:
        del reading_context
        scored = [
            ScoredChunk(chunk=chunk, score=float(score), source="eval-local")
            for score, chunk in _score_local_chunks(query, chunks, course_ids or [], top_k)
        ]
        recorded_searches.append([result.chunk.chunk_id for result in scored])
        return ToolResult(ok=True, value=scored, elapsed_ms=0)

    agent_graph.search_course_material = _search
    try:
        yield recorded_searches
    finally:
        agent_graph.search_course_material = original_search


def _run_agent_case(
    case,
    local_chunks: list[Chunk],
) -> tuple[list[str], list[str], list[str], float | None, bool, str]:
    with _evaluation_search_adapter(local_chunks) as recorded_searches:
        state = agent_graph.run_study_turn(AgentState(session_id=f"eval-{case.case_id}", learning_goal=case.user_input, course_ids=case.course_ids))
        if case.category == "adaptive_review" and state.quiz is not None:
            state.learner_answer = " ".join(state.quiz.expected_points)
            state = agent_graph.run_study_turn(state)
    trace_errors = [f"{trace.tool_name}: {trace.error}" for trace in state.tool_trace if not trace.ok]
    completed = state.status in ("waiting_for_answer", "completed") and not trace_errors
    return (
        [trace.tool_name for trace in state.tool_trace],
        recorded_searches[0][:5] if recorded_searches else [],
        [snapshot.chunk_id for snapshot in state.evidence_snapshots[:3]],
        state.grade.score if state.grade else None,
        completed,
        "; ".join(trace_errors) if trace_errors else "" if completed else state.status,
    )


def run_suite(
    suite: str = "baseline",
    data_dir: str | Path = "data",
    judge: str = "offline",
) -> dict:
    results: list[EvaluationResult] = []
    local_chunks = load_local_chunks(data_dir) if suite == "agent-final" else []
    cases = load_local_rag_cases(data_dir) if suite == "agent-final" and local_chunks else load_cases()
    for case in cases:
        start = time.perf_counter()
        if suite == "agent-final":
            actual_tools, retrieved_citations, actual_citations, score, completed, error = _run_agent_case(
                case,
                local_chunks,
            )
        else:
            actual_tools = list(case.expected_tools)
            retrieved_citations = list(case.required_citations)
            actual_citations = list(case.required_citations)
            score = 0.8 if case.expected_score_band == "high" else 0.6 if case.expected_score_band == "medium" else None
            completed = True
            error = ""
        target_rank = next(
            (
                index + 1
                for index, chunk_id in enumerate(retrieved_citations)
                if chunk_id in set(case.required_citations)
            ),
            None,
        )
        semantic_score = None
        semantic_reason = ""
        if judge == "llm" and actual_citations:
            from final_agent.evaluation.judge import judge_evidence_relevance

            chunk_by_id = {chunk.chunk_id: chunk for chunk in local_chunks}
            evidence_text = [
                chunk_by_id[chunk_id].text
                for chunk_id in actual_citations
                if chunk_id in chunk_by_id
            ]
            judged = judge_evidence_relevance(case.user_input, evidence_text)
            semantic_score = judged["score"]
            semantic_reason = str(judged["reason"])
        results.append(EvaluationResult(
            case_id=case.case_id,
            completed=completed,
            expected_tools=case.expected_tools,
            actual_tools=actual_tools,
            required_citations=case.required_citations,
            retrieved_citations=retrieved_citations,
            actual_citations=actual_citations,
            citation_diagnostics={
                "target_rank": target_rank,
                "query": case.user_input,
            },
            semantic_relevance_score=semantic_score,
            semantic_relevance_reason=semantic_reason,
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
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--judge", default="offline", choices=["offline", "llm"])
    args = parser.parse_args()

    report = run_suite(args.suite, data_dir=args.data_dir, judge=args.judge)
    path = Path("data") / "evaluation" / f"{args.suite}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
