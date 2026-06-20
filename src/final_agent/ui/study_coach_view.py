from __future__ import annotations


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
    parts.extend([
        "",
        f"**Next Action:** `{response.get('next_action', '') or '(pending)'}`",
        "",
        "**Mastery:**",
        *mastery_lines,
    ])
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
