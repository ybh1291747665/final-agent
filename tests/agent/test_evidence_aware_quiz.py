from __future__ import annotations


def test_generate_quiz_accepts_transient_materials():
    from final_agent.agent.tools import generate_quiz

    materials = [
        {
            "heading": "Continuous Integration",
            "text": "Continuous integration runs automated builds and tests after each change.",
        }
    ]

    result = generate_quiz("review CI", [], 1, materials=materials)

    assert result.ok is True
    assert result.value.topic == "review CI"
    assert "Continuous integration" in result.value.prompt
    assert "automated" in result.value.expected_points


def test_generate_quiz_input_schema_carries_materials():
    from final_agent.agent.tools import GenerateQuizInput

    payload = GenerateQuizInput.model_validate(
        {
            "topic": "review CI",
            "course_ids": [],
            "count": 1,
            "materials": [{"text": "CI runs tests."}],
        }
    )

    assert payload.materials == [{"text": "CI runs tests."}]
