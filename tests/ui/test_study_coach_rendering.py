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
