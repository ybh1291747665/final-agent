from __future__ import annotations


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
