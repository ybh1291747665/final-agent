from __future__ import annotations


def test_default_tool_registry_contains_stage_one_tools():
    from final_agent.agent.tool_registry import build_default_tool_registry

    registry = build_default_tool_registry()

    assert sorted(registry.tool_names()) == [
        "generate_quiz",
        "get_learning_profile",
        "grade_answer",
        "search_course_material",
        "summarize_course",
        "update_mastery",
        "verify_evidence",
        "verify_grade_consistency",
    ]
