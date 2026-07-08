from __future__ import annotations


def test_format_study_coach_summary_includes_next_action_and_mastery():
    from final_agent.ui.study_coach_view import format_study_coach_summary

    response = {
        "status": "completed",
        "plan": [
            {
                "objective": "Find relevant course material",
                "tool_name": "search_course_material",
                "completed": False,
            }
        ],
        "quiz": {"prompt": "Explain version control."},
        "grade": {"score": 0.5, "feedback": "Review naming scheme."},
        "next_action": "practice_variant",
    }
    mastery = {
        "configuration management": {"score": 0.5, "attempts": 1},
    }

    content = format_study_coach_summary(response, mastery)

    assert "**Next Action:** `practice_variant`" in content
    assert "- `configuration management`: score=0.50, attempts=1" in content


def test_format_trace_lines_orders_entries():
    from final_agent.ui.study_coach_view import format_trace_lines

    trace = [
        {"sequence_no": 2, "tool_name": "generate_quiz", "ok": True, "elapsed_ms": 1, "error": ""},
        {"sequence_no": 1, "tool_name": "search_course_material", "ok": True, "elapsed_ms": 3, "error": ""},
    ]

    assert format_trace_lines(trace) == [
        "1. `search_course_material` ok in 3 ms",
        "2. `generate_quiz` ok in 1 ms",
    ]


def test_format_study_coach_status_line_names_current_phase():
    from final_agent.ui.study_coach_view import format_study_coach_status_line

    assert format_study_coach_status_line({"status": "waiting_for_answer", "next_action": ""}) == (
        "Coach is waiting for your answer."
    )
    assert format_study_coach_status_line({"status": "completed", "next_action": "practice_variant"}) == (
        "Coach completed this turn; next: practice_variant."
    )


def test_format_mastery_snapshot_highlights_lowest_topic():
    from final_agent.ui.study_coach_view import format_mastery_snapshot

    mastery = {
        "testing": {"score": 0.8, "attempts": 2},
        "branching": {"score": 0.25, "attempts": 1},
    }

    assert format_mastery_snapshot(mastery) == "Lowest mastery: branching at 0.25 after 1 attempt."
    assert format_mastery_snapshot({}) == "No mastery records yet."


def test_format_agent_timeline_includes_role_tool_status_and_latency():
    from final_agent.ui.study_coach_view import format_agent_timeline

    trace = [
        {"sequence_no": 1, "agent_role": "supervisor", "tool_name": "", "ok": True, "elapsed_ms": 0, "output_summary": "Plan ready"},
        {"sequence_no": 2, "agent_role": "retrieval", "tool_name": "search_course_material", "ok": True, "elapsed_ms": 4, "output_summary": "2 chunks"},
    ]

    assert format_agent_timeline(trace) == [
        "1. `supervisor` planned: Plan ready",
        "2. `retrieval` used `search_course_material` ok in 4 ms - 2 chunks",
    ]


def test_format_critic_warnings_keeps_empty_state_clear():
    from final_agent.ui.study_coach_view import format_critic_warnings

    assert format_critic_warnings([]) == ["No critic warnings."]
    assert format_critic_warnings([{"code": "missing_evidence", "message": "No evidence."}]) == [
        "`missing_evidence`: No evidence."
    ]
