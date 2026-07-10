from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from final_agent.agent.models import ToolCall, ToolResult
from final_agent.agent.roles import AgentRole


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input_model: type[BaseModel]
    operation: Callable[[Any], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def execute(self, role: AgentRole, call: ToolCall, *, allowed_tools: list[str]) -> ToolResult:
        started = perf_counter()
        if call.name not in allowed_tools:
            return ToolResult(
                ok=False,
                error=f"Tool '{call.name}' is not allowed for role '{role.value}'",
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        spec = self._tools.get(call.name)
        if spec is None:
            return ToolResult(
                ok=False,
                error=f"Unknown tool '{call.name}'",
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        try:
            payload = spec.input_model.model_validate(call.arguments)
            value = spec.operation(payload)
            return ToolResult(ok=True, value=value, elapsed_ms=int((perf_counter() - started) * 1000))
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                error=f"Validation error: {exc}",
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        except (RuntimeError, ValueError, TimeoutError) as exc:
            return ToolResult(ok=False, error=str(exc), elapsed_ms=int((perf_counter() - started) * 1000))


def build_default_tool_registry(repository=None, quiz_generator=None, grader=None) -> ToolRegistry:
    from final_agent.agent import tools

    def unwrap(result):
        if not result.ok:
            raise RuntimeError(result.error)
        return result.value

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="search_course_material",
            input_model=tools.SearchCourseMaterialInput,
            operation=lambda payload: unwrap(
                tools.search_course_material(
                    payload.query,
                    payload.course_ids,
                    payload.top_k,
                    payload.reading_context,
                )
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="summarize_course",
            input_model=tools.SummarizeCourseInput,
            operation=lambda payload: unwrap(tools.summarize_course(payload.doc_id, payload.mode)),
        )
    )
    registry.register(
        ToolSpec(
            name="generate_quiz",
            input_model=tools.GenerateQuizInput,
            operation=lambda payload: unwrap(
                tools.generate_quiz(
                    payload.topic,
                    payload.course_ids,
                    payload.count,
                    quiz_generator=quiz_generator,
                    materials=payload.materials,
                )
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="grade_answer",
            input_model=tools.GradeAnswerInput,
            operation=lambda payload: unwrap(
                tools.grade_answer(
                    payload.question,
                    payload.expected_points,
                    payload.learner_answer,
                    grader=grader,
                    materials=payload.materials,
                )
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="get_learning_profile",
            input_model=tools.GetLearningProfileInput,
            operation=lambda payload: unwrap(tools.get_learning_profile(payload.session_id, repository)),
        )
    )
    registry.register(
        ToolSpec(
            name="update_mastery",
            input_model=tools.UpdateMasteryInput,
            operation=lambda payload: unwrap(
                tools.update_mastery(payload.session_id, payload.topic, payload.score, repository)
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="verify_evidence",
            input_model=tools.VerifyEvidenceInput,
            operation=lambda payload: unwrap(tools.verify_evidence(payload.quiz_prompt, payload.evidence_count)),
        )
    )
    registry.register(
        ToolSpec(
            name="verify_grade_consistency",
            input_model=tools.VerifyGradeConsistencyInput,
            operation=lambda payload: unwrap(tools.verify_grade_consistency(payload.score, payload.next_action)),
        )
    )
    registry.register(
        ToolSpec(
            name="verify_answer_quality",
            input_model=tools.VerifyAnswerQualityInput,
            operation=lambda payload: unwrap(tools.verify_answer_quality(payload.answer, payload.evidence)),
        )
    )
    return registry
