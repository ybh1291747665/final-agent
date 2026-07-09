# Multi-Agent Study Coach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Stage 1 of Multi-Agent Study Coach: fixed-role orchestration, internal typed tool calling, role-level tool boundaries, compact agent traces, critic warnings, API/UI visibility, and deterministic tests.

**Architecture:** Extend the current bounded Study Coach rather than forking it. Add role and tool-call primitives, route all specialist tool calls through a role-aware `ToolRegistry`, execute the fixed sequence with a new `MultiAgentOrchestrator`, and keep existing `/sessions` behavior backward-compatible while adding agent trace and critic warning fields.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, SQLAlchemy Core, SQLite, Streamlit, pytest, httpx.

---

## File Structure

- Create `src/final_agent/agent/roles.py`: canonical role enum, fixed sequence, role tool allowlist.
- Create `src/final_agent/agent/tool_registry.py`: internal typed tool calling registry, role permission checks, argument validation, execution wrapper.
- Create `src/final_agent/agent/critics.py`: deterministic critic checks for evidence and grade/next-action consistency.
- Create `src/final_agent/agent/orchestrator.py`: fixed sequential multi-agent workflow that wraps current tool/adapters.
- Modify `src/final_agent/agent/models.py`: add `ToolCall`, `AgentToolTraceEntry`, `CriticWarning`, and multi-agent fields on `AgentState`.
- Modify `src/final_agent/agent/tools.py`: add critic input schemas and critic tool functions.
- Modify `src/final_agent/api/schemas.py`: expose backward-compatible `agent_plan`, `agent_trace`, and `critic_warnings`.
- Modify `src/final_agent/api/app.py`: inject and run `MultiAgentOrchestrator` while preserving existing service dependencies.
- Modify `src/final_agent/memory/repository.py`: persist and read agent trace rows with backward-compatible SQLite column migration.
- Modify `src/final_agent/ui/study_coach_view.py`: format agent timeline and critic warnings.
- Modify `src/final_agent/ui/app.py`: show agent timeline and critic warnings in Study Coach/Evidence UI.
- Modify `docs/e2e-acceptance.md`: add multi-agent timeline and critic warning acceptance checks.

---

### Task 1: Role Model And Agent State Extensions

**Files:**
- Create: `src/final_agent/agent/roles.py`
- Modify: `src/final_agent/agent/models.py`
- Test: `tests/agent/test_roles.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_roles.py`:

```python
from __future__ import annotations


def test_agent_roles_have_fixed_stage_one_sequence():
    from final_agent.agent.roles import AgentRole, ROLE_SEQUENCE

    assert ROLE_SEQUENCE == [
        AgentRole.SUPERVISOR,
        AgentRole.RETRIEVAL,
        AgentRole.QUIZ,
        AgentRole.GRADER,
        AgentRole.COACH,
        AgentRole.CRITIC,
    ]


def test_agent_roles_define_allowed_tools():
    from final_agent.agent.roles import AgentRole, allowed_tools_for_role

    assert allowed_tools_for_role(AgentRole.SUPERVISOR) == []
    assert allowed_tools_for_role(AgentRole.RETRIEVAL) == ["search_course_material", "summarize_course"]
    assert allowed_tools_for_role(AgentRole.QUIZ) == ["generate_quiz"]
    assert allowed_tools_for_role(AgentRole.GRADER) == ["grade_answer"]
    assert allowed_tools_for_role(AgentRole.COACH) == ["get_learning_profile", "update_mastery"]
    assert allowed_tools_for_role(AgentRole.CRITIC) == ["verify_evidence", "verify_grade_consistency"]


def test_agent_state_carries_multi_agent_fields():
    from final_agent.agent.models import AgentState

    state = AgentState(session_id="s1", learning_goal="review CI")

    assert state.agent_plan == []
    assert state.agent_trace == []
    assert state.critic_warnings == []
    assert state.current_agent_role == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_roles.py -q
```

Expected: FAIL because `final_agent.agent.roles` and the new `AgentState` fields do not exist.

- [ ] **Step 3: Implement role and state models**

Create `src/final_agent/agent/roles.py`:

```python
from __future__ import annotations

from enum import StrEnum


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    RETRIEVAL = "retrieval"
    QUIZ = "quiz"
    GRADER = "grader"
    COACH = "coach"
    CRITIC = "critic"


ROLE_SEQUENCE: list[AgentRole] = [
    AgentRole.SUPERVISOR,
    AgentRole.RETRIEVAL,
    AgentRole.QUIZ,
    AgentRole.GRADER,
    AgentRole.COACH,
    AgentRole.CRITIC,
]


ROLE_ALLOWED_TOOLS: dict[AgentRole, list[str]] = {
    AgentRole.SUPERVISOR: [],
    AgentRole.RETRIEVAL: ["search_course_material", "summarize_course"],
    AgentRole.QUIZ: ["generate_quiz"],
    AgentRole.GRADER: ["grade_answer"],
    AgentRole.COACH: ["get_learning_profile", "update_mastery"],
    AgentRole.CRITIC: ["verify_evidence", "verify_grade_consistency"],
}


def allowed_tools_for_role(role: AgentRole) -> list[str]:
    return list(ROLE_ALLOWED_TOOLS[role])
```

Modify `src/final_agent/agent/models.py`:

```python
from final_agent.agent.roles import AgentRole
```

Add after `ToolResult`:

```python
class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentToolTraceEntry(BaseModel):
    agent_role: AgentRole
    tool_name: str = ""
    input_summary: str = ""
    output_summary: str = ""
    ok: bool = True
    elapsed_ms: int = 0
    error: str = ""
    fallback_reason: str = ""
    sequence_no: int = 0


class CriticWarning(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning"] = "warning"
```

Add fields to `AgentState`:

```python
    agent_plan: list[str] = Field(default_factory=list)
    agent_trace: list[AgentToolTraceEntry] = Field(default_factory=list)
    critic_warnings: list[CriticWarning] = Field(default_factory=list)
    current_agent_role: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_roles.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/roles.py src/final_agent/agent/models.py tests/agent/test_roles.py
git commit -m "feat: add multi-agent role models"
```

---

### Task 2: Internal Typed Tool Registry

**Files:**
- Create: `src/final_agent/agent/tool_registry.py`
- Test: `tests/agent/test_tool_registry.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_tool_registry.py`:

```python
from __future__ import annotations

import pytest
from pydantic import BaseModel


class EchoInput(BaseModel):
    text: str


def test_tool_registry_executes_allowed_tool():
    from final_agent.agent.models import ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            input_model=EchoInput,
            operation=lambda payload: payload.text.upper(),
        )
    )

    result = registry.execute(AgentRole.RETRIEVAL, ToolCall(name="echo", arguments={"text": "ci"}), allowed_tools=["echo"])

    assert result.ok is True
    assert result.value == "CI"


def test_tool_registry_rejects_unauthorized_tool():
    from final_agent.agent.models import ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", input_model=EchoInput, operation=lambda payload: payload.text))

    result = registry.execute(AgentRole.SUPERVISOR, ToolCall(name="echo", arguments={"text": "ci"}), allowed_tools=[])

    assert result.ok is False
    assert "not allowed" in result.error


def test_tool_registry_rejects_invalid_arguments():
    from final_agent.agent.models import ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", input_model=EchoInput, operation=lambda payload: payload.text))

    result = registry.execute(AgentRole.RETRIEVAL, ToolCall(name="echo", arguments={}), allowed_tools=["echo"])

    assert result.ok is False
    assert "validation" in result.error.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_tool_registry.py -q
```

Expected: FAIL because `tool_registry.py` does not exist.

- [ ] **Step 3: Implement the registry**

Create `src/final_agent/agent/tool_registry.py`:

```python
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
            return ToolResult(ok=False, error=f"Validation error: {exc}", elapsed_ms=int((perf_counter() - started) * 1000))
        except (RuntimeError, ValueError, TimeoutError) as exc:
            return ToolResult(ok=False, error=str(exc), elapsed_ms=int((perf_counter() - started) * 1000))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_tool_registry.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/tool_registry.py tests/agent/test_tool_registry.py
git commit -m "feat: add typed tool registry"
```

---

### Task 3: Critic Tools

**Files:**
- Create: `src/final_agent/agent/critics.py`
- Modify: `src/final_agent/agent/tools.py`
- Test: `tests/agent/test_critics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_critics.py`:

```python
from __future__ import annotations


def test_verify_evidence_warns_when_quiz_has_no_materials():
    from final_agent.agent.critics import verify_evidence

    warnings = verify_evidence(quiz_prompt="Explain CI.", evidence_count=0)

    assert [warning.code for warning in warnings] == ["missing_evidence"]


def test_verify_grade_consistency_warns_when_next_action_conflicts_with_score():
    from final_agent.agent.critics import verify_grade_consistency

    warnings = verify_grade_consistency(score=0.2, next_action="advance_topic")

    assert [warning.code for warning in warnings] == ["next_action_score_mismatch"]


def test_verify_grade_consistency_accepts_matching_score_and_action():
    from final_agent.agent.critics import verify_grade_consistency

    assert verify_grade_consistency(score=0.9, next_action="advance_topic") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_critics.py -q
```

Expected: FAIL because `critics.py` does not exist.

- [ ] **Step 3: Implement deterministic critic functions and tool wrappers**

Create `src/final_agent/agent/critics.py`:

```python
from __future__ import annotations

from final_agent.agent.models import CriticWarning


def verify_evidence(*, quiz_prompt: str, evidence_count: int) -> list[CriticWarning]:
    if quiz_prompt and evidence_count <= 0:
        return [
            CriticWarning(
                code="missing_evidence",
                message="Quiz was generated without retrieved course evidence.",
            )
        ]
    return []


def verify_grade_consistency(*, score: float, next_action: str) -> list[CriticWarning]:
    if score < 0.4 and next_action != "re_explain":
        return [
            CriticWarning(
                code="next_action_score_mismatch",
                message="Low score should usually lead to re_explain.",
            )
        ]
    if score > 0.7 and next_action != "advance_topic":
        return [
            CriticWarning(
                code="next_action_score_mismatch",
                message="High score should usually lead to advance_topic.",
            )
        ]
    return []
```

Modify `src/final_agent/agent/tools.py`:

```python
from final_agent.agent.critics import verify_evidence as critic_verify_evidence
from final_agent.agent.critics import verify_grade_consistency as critic_verify_grade_consistency
```

Add input schemas:

```python
class VerifyEvidenceInput(BaseModel):
    quiz_prompt: str = ""
    evidence_count: int = 0


class VerifyGradeConsistencyInput(BaseModel):
    score: float
    next_action: str
```

Add tool functions:

```python
def verify_evidence(quiz_prompt: str, evidence_count: int) -> ToolResult:
    return run_tool(lambda: critic_verify_evidence(quiz_prompt=quiz_prompt, evidence_count=evidence_count))


def verify_grade_consistency(score: float, next_action: str) -> ToolResult:
    return run_tool(lambda: critic_verify_grade_consistency(score=score, next_action=next_action))
```

Extend `TOOL_REGISTRY`:

```python
    "verify_evidence": VerifyEvidenceInput,
    "verify_grade_consistency": VerifyGradeConsistencyInput,
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_critics.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/critics.py src/final_agent/agent/tools.py tests/agent/test_critics.py
git commit -m "feat: add critic tools"
```

---

### Task 4: Default Registry For Existing Tools

**Files:**
- Modify: `src/final_agent/agent/tool_registry.py`
- Test: `tests/agent/test_tool_registry_defaults.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_tool_registry_defaults.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/agent/test_tool_registry_defaults.py -q
```

Expected: FAIL because `build_default_tool_registry` and `tool_names` do not exist.

- [ ] **Step 3: Add default registry construction**

Modify `src/final_agent/agent/tool_registry.py`:

```python
    def tool_names(self) -> list[str]:
        return sorted(self._tools)
```

Add:

```python
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
            operation=lambda payload: unwrap(tools.search_course_material(payload.query, payload.course_ids, payload.top_k)),
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
            operation=lambda payload: unwrap(tools.generate_quiz(payload.topic, payload.course_ids, payload.count, quiz_generator=quiz_generator)),
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
            operation=lambda payload: unwrap(tools.update_mastery(payload.session_id, payload.topic, payload.score, repository)),
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
    return registry
```

Modify `src/final_agent/agent/tools.py` to add missing schemas:

```python
class GradeAnswerInput(BaseModel):
    question: str
    expected_points: list[str] = Field(default_factory=list)
    learner_answer: str
    materials: list[Any] = Field(default_factory=list)


class GetLearningProfileInput(BaseModel):
    session_id: str


class UpdateMasteryInput(BaseModel):
    session_id: str
    topic: str
    score: float
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/agent/test_tool_registry_defaults.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/tool_registry.py src/final_agent/agent/tools.py tests/agent/test_tool_registry_defaults.py
git commit -m "feat: register study coach tools"
```

---

### Task 5: Multi-Agent Orchestrator

**Files:**
- Create: `src/final_agent/agent/orchestrator.py`
- Test: `tests/agent/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_orchestrator.py`:

```python
from __future__ import annotations


def test_orchestrator_initial_turn_runs_supervisor_retrieval_and_quiz():
    from final_agent.agent.models import AgentState
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.roles import AgentRole

    state = MultiAgentOrchestrator().run_turn(AgentState(session_id="s1", learning_goal="review CI"))

    assert state.status == "waiting_for_answer"
    assert state.quiz is not None
    assert [entry.agent_role for entry in state.agent_trace] == [
        AgentRole.SUPERVISOR,
        AgentRole.RETRIEVAL,
        AgentRole.QUIZ,
    ]


def test_orchestrator_answer_turn_runs_grader_coach_and_critic_without_blocking():
    from final_agent.agent.models import AgentState, QuizQuestion
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.roles import AgentRole

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        status="waiting_for_answer",
        quiz=QuizQuestion(question_id="q1", topic="review CI", prompt="Explain CI.", expected_points=["automation"]),
        learner_answer="automation matters",
    )

    updated = MultiAgentOrchestrator().run_turn(state)

    assert updated.status == "completed"
    assert updated.grade is not None
    assert [entry.agent_role for entry in updated.agent_trace] == [
        AgentRole.GRADER,
        AgentRole.COACH,
        AgentRole.CRITIC,
        AgentRole.CRITIC,
    ]
    assert updated.critic_warnings
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_orchestrator.py -q
```

Expected: FAIL because `orchestrator.py` does not exist.

- [ ] **Step 3: Implement orchestrator**

Create `src/final_agent/agent/orchestrator.py`:

```python
from __future__ import annotations

from final_agent.agent.mastery import choose_learning_action
from final_agent.agent.models import AgentState, AgentToolTraceEntry, CriticWarning, ToolCall
from final_agent.agent.roles import AgentRole, ROLE_SEQUENCE, allowed_tools_for_role
from final_agent.agent.tool_registry import ToolRegistry, build_default_tool_registry


MAX_TOOL_CALLS = 6


class MultiAgentOrchestrator:
    def __init__(self, registry: ToolRegistry | None = None, repository=None, quiz_generator=None, grader=None):
        self.repository = repository
        self.registry = registry or build_default_tool_registry(repository=repository, quiz_generator=quiz_generator, grader=grader)

    def _append_trace(
        self,
        state: AgentState,
        *,
        role: AgentRole,
        tool_name: str = "",
        input_summary: str = "",
        output_summary: str = "",
        ok: bool = True,
        elapsed_ms: int = 0,
        error: str = "",
        fallback_reason: str = "",
    ) -> None:
        state.agent_trace.append(
            AgentToolTraceEntry(
                agent_role=role,
                tool_name=tool_name,
                input_summary=input_summary,
                output_summary=output_summary,
                ok=ok,
                elapsed_ms=elapsed_ms,
                error=error,
                fallback_reason=fallback_reason,
                sequence_no=len(state.agent_trace) + 1,
            )
        )
        if tool_name:
            state.tool_call_count += 1

    def _execute(self, state: AgentState, role: AgentRole, call: ToolCall):
        result = self.registry.execute(role, call, allowed_tools=allowed_tools_for_role(role))
        self._append_trace(
            state,
            role=role,
            tool_name=call.name,
            input_summary=str(call.arguments)[:160],
            output_summary=str(result.value)[:160] if result.ok else "",
            ok=result.ok,
            elapsed_ms=result.elapsed_ms,
            error=result.error,
        )
        return result

    def run_turn(self, state: AgentState) -> AgentState:
        if state.tool_call_count >= MAX_TOOL_CALLS:
            state.status = "failed"
            return state
        state.agent_plan = [role.value for role in ROLE_SEQUENCE]
        if state.status in ("planning", "running"):
            state.status = "running"
            self._append_trace(state, role=AgentRole.SUPERVISOR, output_summary="Fixed sequential plan prepared.")
            retrieval = self._execute(
                state,
                AgentRole.RETRIEVAL,
                ToolCall(name="search_course_material", arguments={"query": state.learning_goal, "course_ids": state.course_ids, "top_k": 5}),
            )
            quiz = self._execute(
                state,
                AgentRole.QUIZ,
                ToolCall(name="generate_quiz", arguments={"topic": state.learning_goal, "course_ids": state.course_ids, "count": 1}),
            )
            if not retrieval.ok or not quiz.ok:
                state.status = "failed"
                return state
            state.quiz = quiz.value
            state.status = "waiting_for_answer"
            return state
        if state.status == "waiting_for_answer":
            if not state.learner_answer:
                return state
            if state.quiz is None:
                state.status = "failed"
                return state
            grade = self._execute(
                state,
                AgentRole.GRADER,
                ToolCall(
                    name="grade_answer",
                    arguments={
                        "question": state.quiz.prompt,
                        "expected_points": state.quiz.expected_points,
                        "learner_answer": state.learner_answer,
                        "materials": [],
                    },
                ),
            )
            if not grade.ok:
                state.status = "failed"
                return state
            state.grade = grade.value
            if self.repository is not None:
                self.repository.save_attempt(state.session_id, state.quiz, state.learner_answer, state.grade)
            state.next_action = choose_learning_action(state.grade.score)
            mastery = self._execute(
                state,
                AgentRole.COACH,
                ToolCall(name="update_mastery", arguments={"session_id": state.session_id, "topic": state.quiz.topic, "score": state.grade.score}),
            )
            if not mastery.ok:
                state.status = "failed"
                return state
            evidence = self._execute(
                state,
                AgentRole.CRITIC,
                ToolCall(name="verify_evidence", arguments={"quiz_prompt": state.quiz.prompt, "evidence_count": 0}),
            )
            consistency = self._execute(
                state,
                AgentRole.CRITIC,
                ToolCall(name="verify_grade_consistency", arguments={"score": state.grade.score, "next_action": state.next_action}),
            )
            warnings: list[CriticWarning] = []
            if evidence.ok:
                warnings.extend(evidence.value)
            if consistency.ok:
                warnings.extend(consistency.value)
            state.critic_warnings = warnings
            state.status = "completed"
            return state
        return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat: add multi-agent orchestrator"
```

---

### Task 6: API Backward-Compatible Response Extensions

**Files:**
- Modify: `src/final_agent/api/schemas.py`
- Modify: `src/final_agent/api/app.py`
- Test: `tests/api/test_multi_agent_sessions.py`
- Modify test: `tests/api/test_sessions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_multi_agent_sessions.py`:

```python
from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_session_response_exposes_agent_trace_and_warnings(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/sessions", json={"learning_goal": "review CI", "course_ids": []})
        assert created.status_code == 201
        body = created.json()

    assert "agent_plan" in body
    assert "agent_trace" in body
    assert "critic_warnings" in body
    assert [entry["agent_role"] for entry in body["agent_trace"]] == ["supervisor", "retrieval", "quiz"]
```

Modify the dependency injection tests in `tests/api/test_sessions.py` so they assert orchestrator injection rather than monkeypatching `run_study_turn`:

```python
def test_agent_service_uses_injected_orchestrator(tmp_path):
    from final_agent.api.app import AgentService
    from final_agent.api.schemas import CreateSessionRequest
    from final_agent.memory.repository import MemoryRepository

    class FakeOrchestrator:
        def __init__(self):
            self.called = False

        def run_turn(self, state):
            self.called = True
            state.status = "waiting_for_answer"
            return state

    orchestrator = FakeOrchestrator()
    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"), orchestrator=orchestrator)
    service.create_session(CreateSessionRequest(learning_goal="review CI", course_ids=[]))

    assert orchestrator.called is True
```

Remove the old assertions that monkeypatch `final_agent.api.app.run_study_turn`; `AgentService` no longer calls that function after this task.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_multi_agent_sessions.py -q
```

Expected: FAIL because API responses do not expose multi-agent fields and `AgentService` does not yet run the orchestrator.

- [ ] **Step 3: Extend schemas and service**

Modify `src/final_agent/api/schemas.py` imports:

```python
from final_agent.agent.models import AgentStatus, AgentToolTraceEntry, CriticWarning, GradeResult, QuizQuestion, StudyPlanStep
```

Add to `SessionResponse`:

```python
    agent_plan: list[str] = Field(default_factory=list)
    agent_trace: list[AgentToolTraceEntry] = Field(default_factory=list)
    critic_warnings: list[CriticWarning] = Field(default_factory=list)
```

Modify `src/final_agent/api/app.py`:

```python
from final_agent.agent.orchestrator import MultiAgentOrchestrator
```

Update `AgentService.__init__`:

```python
    def __init__(self, repository: MemoryRepository, quiz_generator=None, grader=None, orchestrator=None):
        self.repository = repository
        self.quiz_generator = select_quiz_generator(load_settings()) if quiz_generator is None else quiz_generator
        self.grader = LlmGrader(fallback=DeterministicGrader()) if grader is None else grader
        self.orchestrator = orchestrator or MultiAgentOrchestrator(
            repository=repository,
            quiz_generator=self.quiz_generator,
            grader=self.grader,
        )
```

Update `_response`:

```python
            agent_plan=state.agent_plan,
            agent_trace=state.agent_trace,
            critic_warnings=state.critic_warnings,
```

Replace `run_study_turn(...)` calls in `create_session` and `send_message`:

```python
        state = self.orchestrator.run_turn(state)
```

Update `create_app`:

```python
def create_app(repository: MemoryRepository | None = None, quiz_generator=None, grader=None, orchestrator=None) -> FastAPI:
    app = FastAPI(title="final-agent Study Coach API")
    repo = MemoryRepository() if repository is None else repository
    service = AgentService(repo, quiz_generator=quiz_generator, grader=grader, orchestrator=orchestrator)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/api/test_multi_agent_sessions.py tests/api/test_sessions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/api/schemas.py src/final_agent/api/app.py tests/api/test_multi_agent_sessions.py tests/api/test_sessions.py
git commit -m "feat: expose multi-agent session fields"
```

---

### Task 7: Persist Agent Trace

**Files:**
- Modify: `src/final_agent/memory/repository.py`
- Test: `tests/memory/test_agent_trace_repository.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/memory/test_agent_trace_repository.py`:

```python
from __future__ import annotations


def test_repository_persists_agent_trace(tmp_path):
    from final_agent.agent.models import AgentToolTraceEntry
    from final_agent.agent.roles import AgentRole
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "memory.sqlite")

    repo.append_agent_trace(
        "s1",
        AgentToolTraceEntry(
            agent_role=AgentRole.RETRIEVAL,
            tool_name="search_course_material",
            input_summary="review CI",
            output_summary="2 chunks",
            ok=True,
            elapsed_ms=3,
            fallback_reason="",
        ),
    )

    trace = repo.list_agent_trace("s1")

    assert len(trace) == 1
    assert trace[0].sequence_no == 1
    assert trace[0].agent_role == AgentRole.RETRIEVAL
    assert trace[0].tool_name == "search_course_material"
    assert trace[0].output_summary == "2 chunks"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/memory/test_agent_trace_repository.py -q
```

Expected: FAIL because repository has no agent trace persistence methods or columns.

- [ ] **Step 3: Add agent trace columns and methods**

Modify `tool_traces` in `src/final_agent/memory/repository.py`:

```python
    Column("agent_role", String, nullable=False, default=""),
    Column("output_summary", Text, nullable=False, default=""),
    Column("fallback_reason", Text, nullable=False, default=""),
```

Import:

```python
from final_agent.agent.models import AgentState, AgentToolTraceEntry, GradeResult, MasteryRecord, QuizQuestion, ToolTraceEntry
from final_agent.agent.roles import AgentRole
```

Add migration helper:

```python
def _ensure_tool_trace_columns(engine: Engine) -> None:
    required = {
        "agent_role": "TEXT NOT NULL DEFAULT ''",
        "output_summary": "TEXT NOT NULL DEFAULT ''",
        "fallback_reason": "TEXT NOT NULL DEFAULT ''",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tool_traces)").fetchall()}
        for name, ddl in required.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE tool_traces ADD COLUMN {name} {ddl}")
```

Call it in `MemoryRepository.__init__` after `metadata.create_all(self.engine)`:

```python
        _ensure_tool_trace_columns(self.engine)
```

Add methods:

```python
    def append_agent_trace(self, session_id: str, trace: AgentToolTraceEntry) -> AgentToolTraceEntry:
        with self.engine.begin() as conn:
            current = conn.execute(
                select(tool_traces.c.sequence_no)
                .where(tool_traces.c.session_id == session_id)
                .order_by(tool_traces.c.sequence_no.desc())
            ).first()
            sequence_no = (current[0] + 1) if current else 1
            conn.execute(tool_traces.insert().values(
                session_id=session_id,
                sequence_no=sequence_no,
                tool_name=trace.tool_name,
                input_summary=trace.input_summary,
                ok=trace.ok,
                elapsed_ms=trace.elapsed_ms,
                error=trace.error,
                agent_role=trace.agent_role.value,
                output_summary=trace.output_summary,
                fallback_reason=trace.fallback_reason,
                created_at=_now(),
            ))
        trace.sequence_no = sequence_no
        return trace

    def list_agent_trace(self, session_id: str) -> list[AgentToolTraceEntry]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(tool_traces)
                .where(tool_traces.c.session_id == session_id)
                .order_by(tool_traces.c.sequence_no)
            ).mappings().all()
        return [
            AgentToolTraceEntry(
                agent_role=AgentRole(row["agent_role"] or AgentRole.SUPERVISOR.value),
                tool_name=row["tool_name"],
                input_summary=row["input_summary"],
                output_summary=row["output_summary"] or "",
                ok=row["ok"],
                elapsed_ms=row["elapsed_ms"],
                error=row["error"],
                fallback_reason=row["fallback_reason"] or "",
                sequence_no=row["sequence_no"],
            )
            for row in rows
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/memory/test_agent_trace_repository.py tests/memory/test_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/memory/repository.py tests/memory/test_agent_trace_repository.py
git commit -m "feat: persist agent tool trace"
```

---

### Task 8: API Service Persists Agent Trace

**Files:**
- Modify: `src/final_agent/api/app.py`
- Test: `tests/api/test_multi_agent_trace_persistence.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_multi_agent_trace_persistence.py`:

```python
from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_api_persists_agent_trace_rows(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    repo = MemoryRepository(tmp_path / "api.sqlite")
    app = create_app(repository=repo)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/sessions", json={"learning_goal": "review CI", "course_ids": []})
        session_id = created.json()["session_id"]

    trace = repo.list_agent_trace(session_id)

    assert [entry.agent_role.value for entry in trace] == ["supervisor", "retrieval", "quiz"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_multi_agent_trace_persistence.py -q
```

Expected: FAIL because `AgentService` does not persist `state.agent_trace` rows separately.

- [ ] **Step 3: Persist new agent trace entries**

Modify `src/final_agent/api/app.py`.

In `create_session`, after `self.repository.create_session(state)`:

```python
        for trace in state.agent_trace:
            self.repository.append_agent_trace(state.session_id, trace)
```

In `send_message`, before running orchestrator:

```python
        before_agent_trace = len(state.agent_trace)
```

After `self.repository.save_session(state)`:

```python
        for trace in state.agent_trace[before_agent_trace:]:
            self.repository.append_agent_trace(state.session_id, trace)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/api/test_multi_agent_trace_persistence.py tests/api/test_sessions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/api/app.py tests/api/test_multi_agent_trace_persistence.py
git commit -m "feat: persist agent trace from API"
```

---

### Task 9: Streamlit Timeline And Critic Warning Formatting

**Files:**
- Modify: `src/final_agent/ui/study_coach_view.py`
- Modify: `src/final_agent/ui/app.py`
- Test: `tests/ui/test_study_coach_rendering.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_study_coach_rendering.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/ui/test_study_coach_rendering.py::test_format_agent_timeline_includes_role_tool_status_and_latency tests/ui/test_study_coach_rendering.py::test_format_critic_warnings_keeps_empty_state_clear -q
```

Expected: FAIL because the new formatting helpers do not exist.

- [ ] **Step 3: Implement formatting helpers and UI rendering**

Modify `src/final_agent/ui/study_coach_view.py`:

```python
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
```

Modify `src/final_agent/ui/app.py` import:

```python
from final_agent.ui.study_coach_view import (
    format_agent_timeline,
    format_critic_warnings,
    format_study_coach_summary,
    format_trace_lines,
)
```

In `_run_study_coach_turn`, after trace response rendering:

```python
        with st.expander("Multi-Agent timeline", expanded=False):
            for line in format_agent_timeline(response.get("agent_trace", [])):
                st.markdown(f"- {line}")
        with st.expander("Critic warnings", expanded=False):
            for line in format_critic_warnings(response.get("critic_warnings", [])):
                st.markdown(f"- {line}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/ui/test_study_coach_rendering.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/ui/study_coach_view.py src/final_agent/ui/app.py tests/ui/test_study_coach_rendering.py
git commit -m "feat: show multi-agent timeline"
```

---

### Task 10: Acceptance Docs And Full Verification

**Files:**
- Modify: `docs/e2e-acceptance.md`
- Test: `tests/docs/test_acceptance_docs.py`

- [ ] **Step 1: Write the failing doc test**

Modify `tests/docs/test_acceptance_docs.py`:

```python
def test_acceptance_runbook_covers_multi_agent_stage_one_flow():
    text = Path("docs/e2e-acceptance.md").read_text(encoding="utf-8")

    assert "Multi-Agent timeline" in text
    assert "Supervisor" in text
    assert "Retrieval" in text
    assert "Quiz" in text
    assert "Grader" in text
    assert "Coach" in text
    assert "Critic" in text
    assert "Critic warnings" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/docs/test_acceptance_docs.py::test_acceptance_runbook_covers_multi_agent_stage_one_flow -q
```

Expected: FAIL because the runbook does not yet mention the multi-agent timeline and critic warning checks.

- [ ] **Step 3: Update acceptance runbook**

Modify `docs/e2e-acceptance.md` Study Coach section:

```markdown
8. Open `Multi-Agent timeline`.
9. Confirm the timeline includes Supervisor, Retrieval, Quiz, Grader, Coach, and Critic in order after a complete turn.
10. Open `Critic warnings`.
11. Confirm warnings are visible when present and the session can still complete.
```

- [ ] **Step 4: Run targeted and full verification**

Run:

```bash
pytest tests/docs/test_acceptance_docs.py -q
pytest tests/agent tests/api tests/memory tests/ui tests/docs -q
python -m compileall -q src tests
pytest -q
```

Expected: all commands exit 0. Existing third-party deprecation warnings may remain, but there must be no test failures.

- [ ] **Step 5: Commit**

```bash
git add docs/e2e-acceptance.md tests/docs/test_acceptance_docs.py
git commit -m "docs: add multi-agent acceptance checks"
```

---

## Self-Review Checklist

- Spec coverage: The plan covers role model, tool calling, role boundaries, orchestrator, trace persistence, API compatibility, UI visibility, critic warnings, docs, and deterministic verification.
- Scope control: The plan excludes LLM autonomous planning, provider-native function calling, parallel execution, retry loops, and new `/multi-agent/*` endpoints.
- Type consistency: The plan consistently uses `AgentRole`, `ToolCall`, `ToolSpec`, `ToolRegistry`, `AgentToolTraceEntry`, `CriticWarning`, and `MultiAgentOrchestrator`.
- Backward compatibility: The plan keeps old session endpoints and old `tool_trace` behavior while adding `agent_trace` and `critic_warnings`.
- Test order: Every production change is preceded by a failing test command.
