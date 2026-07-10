from __future__ import annotations

from pathlib import Path


def _format_evidence_label(snapshot: dict) -> str:
    source_path = str(snapshot.get("source_path", "") or "")
    doc_id = str(snapshot.get("doc_id", "") or "")
    chunk_id = str(snapshot.get("chunk_id", "") or "")
    file_name = Path(source_path).name if source_path else doc_id
    page_num = snapshot.get("page_num")

    try:
        page = int(page_num) if page_num not in (None, "") else 0
    except (TypeError, ValueError):
        page = 0

    if file_name and page > 0:
        return f"{file_name}，第 {page} 页"
    if file_name:
        return file_name
    if page > 0:
        return f"第 {page} 页"
    return f"chunk {chunk_id[:8]}"


def format_evidence_snapshots(snapshots: list[dict]) -> list[str]:
    if not snapshots:
        return ["No evidence snapshots yet."]

    lines: list[str] = []
    for snapshot in snapshots:
        label = _format_evidence_label(snapshot)
        heading = str(snapshot.get("heading", "") or "")
        score = float(snapshot.get("score", 0.0))
        summary = str(snapshot.get("summary", "") or "")
        heading_part = f" · {heading}" if heading else ""
        lines.append(f"**{label}**{heading_part} · score={score:.2f}\n{summary}")
    return lines


def format_study_coach_status_line(response: dict) -> str:
    status = response.get("status", "")
    next_action = response.get("next_action", "")
    if status == "waiting_for_answer":
        return "Coach is waiting for your answer."
    if status == "completed":
        return f"Coach completed this turn; next: {next_action or 'review'}."
    return f"Coach status: {status or 'unknown'}."


def format_mastery_snapshot(mastery: dict[str, dict] | None = None) -> str:
    mastery = mastery or {}
    if not mastery:
        return "No mastery records yet."
    topic, record = min(
        mastery.items(),
        key=lambda item: (float(item[1].get("score", 0.0)), item[0]),
    )
    attempts = int(record.get("attempts", 0))
    noun = "attempt" if attempts == 1 else "attempts"
    return f"Lowest mastery: {topic} at {float(record.get('score', 0.0)):.2f} after {attempts} {noun}."


def format_study_coach_summary(response: dict, mastery: dict[str, dict] | None = None) -> str:
    plan_lines = [
        f"- [{'x' if step.get('completed') else ' '}] {step.get('objective', '')} (`{step.get('tool_name', '')}`)"
        for step in response.get("plan", [])
    ] or ["- `(no plan)`"]
    quiz = response.get("quiz") or {}
    grade = response.get("grade") or {}
    mastery = mastery or {}
    mastery_lines = [
        f"- `{topic}`: score={float(record.get('score', 0.0)):.2f}, attempts={int(record.get('attempts', 0))}"
        for topic, record in sorted(mastery.items())
    ] or ["- `(none yet)`"]
    grade_score = grade.get("score", "waiting")
    feedback = grade.get("feedback", "")
    parts = [
        format_study_coach_status_line(response),
        format_mastery_snapshot(mastery),
        "",
        f"**Status:** `{response.get('status')}`",
        "",
        "**Plan:**",
        *plan_lines,
        "",
        f"**Question:** {quiz.get('prompt', '(none)')}",
        f"**Grade:** {grade_score}",
    ]
    if feedback:
        parts.append(feedback)
    parts.extend(
        [
            "",
            f"**Next Action:** `{response.get('next_action', '') or '(pending)'}`",
            "",
            "**Mastery:**",
            *mastery_lines,
        ]
    )
    return "\n".join(parts)


def format_trace_lines(trace: list[dict]) -> list[str]:
    lines: list[str] = []
    for entry in sorted(trace, key=lambda item: item.get("sequence_no", 0)):
        status = "ok" if entry.get("ok") else "error"
        detail = f"{entry.get('sequence_no', '?')}. `{entry.get('tool_name', '')}` {status} in {entry.get('elapsed_ms', 0)} ms"
        if entry.get("error"):
            detail += f" - {entry['error']}"
        lines.append(detail)
    return lines


def format_agent_timeline(trace: list[dict]) -> list[str]:
    if not trace:
        return ["No agent trace yet."]
    lines: list[str] = []
    for entry in sorted(trace, key=lambda item: item.get("sequence_no", 0)):
        role = entry.get("agent_role", "")
        tool = entry.get("tool_name", "")
        ok = "ok" if entry.get("ok", True) else "error"
        elapsed_ms = int(entry.get("elapsed_ms", 0))
        output = entry.get("output_summary", "")
        if tool:
            suffix = f" - {output}" if output else ""
            lines.append(f"{entry.get('sequence_no', '?')}. `{role}` used `{tool}` {ok} in {elapsed_ms} ms{suffix}")
        else:
            lines.append(f"{entry.get('sequence_no', '?')}. `{role}` planned: {output}")
    return lines


def format_critic_warnings(warnings: list[dict]) -> list[str]:
    if not warnings:
        return ["No critic warnings."]
    return [f"`{warning.get('code', 'warning')}`: {warning.get('message', '')}" for warning in warnings]


def format_quality_report(report: dict | None) -> list[str]:
    if not report:
        return ["No answer quality report yet."]
    status = "needs revision" if report.get("needs_revision") else "grounded"
    lines = [
        f"Status: `{status}`",
        f"Citations: {int(report.get('citation_count', 0))}",
        f"Evidence items: {int(report.get('evidence_count', 0))}",
        f"Uncited claims: {int(report.get('missing_citation_count', 0))}",
        f"Unsupported citations: {int(report.get('unsupported_citation_count', 0))}",
    ]
    warnings = report.get("warnings") or []
    if warnings:
        lines.append("Warnings: " + ", ".join(f"`{warning}`" for warning in warnings))
    return lines
