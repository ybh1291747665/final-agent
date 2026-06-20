from __future__ import annotations

from final_agent.evaluation.models import EvaluationCase


def load_cases() -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for i in range(10):
        cases.append(EvaluationCase(
            case_id=f"retrieval-{i + 1:02d}",
            category="retrieval",
            course_ids=["fixture-course"],
            user_input=f"Find concept {i + 1}",
            expected_tools=["search_course_material"],
            required_citations=[f"fixture-{i + 1:02d}"],
            expected_outcome="Retrieve a grounded course-material answer.",
        ))
    for i in range(10):
        cases.append(EvaluationCase(
            case_id=f"tool-{i + 1:02d}",
            category="tool_selection",
            course_ids=["fixture-course"],
            user_input=f"Create a quiz for topic {i + 1}",
            expected_tools=["search_course_material", "generate_quiz"],
            expected_outcome="Select the retrieval and quiz tools in order.",
        ))
    for i in range(10):
        cases.append(EvaluationCase(
            case_id=f"adaptive-{i + 1:02d}",
            category="adaptive_review",
            course_ids=["fixture-course"],
            user_input=f"Grade answer for topic {i + 1}",
            expected_tools=["grade_answer", "update_mastery"],
            expected_outcome="Grade the learner answer and update mastery.",
            expected_score_band="high" if i % 2 == 0 else "medium",
        ))
    return cases
