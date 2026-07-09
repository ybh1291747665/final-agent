# Grader Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an injectable grader adapter with deterministic and LLM-backed implementations while preserving the existing `GradeResult` contract and outward Study Coach behavior.

**Architecture:** Add a dedicated `graders` module containing deterministic and LLM-backed grading implementations plus lightweight grading metadata. Inject the selected grader from app/service into the workflow, keep fallback inside the LLM adapter, and preserve existing API/UI payloads while exposing implementation choice through existing trace fields.

**Tech Stack:** Python, Pydantic, OpenAI-compatible LLM client, FastAPI, pytest

---

## File Map

- Create: `src/final_agent/agent/graders.py`
  - Define grading metadata, deterministic grading, and LLM-backed grading with fallback.
- Modify: `src/final_agent/agent/tools.py`
  - Delegate grading to an injected grader instead of hard-coded point matching.
- Modify: `src/final_agent/agent/graph.py`
  - Accept an injected grader and carry grading implementation metadata into the trace.
- Modify: `src/final_agent/api/app.py`
  - Assemble and pass the default grader from app/service.
- Create: `tests/agent/test_graders.py`
  - Verify deterministic grading, LLM success, and fallback behavior.
- Modify: `tests/agent/test_tools.py`
  - Verify `grade_answer` delegates to the provided grader.
- Modify: `tests/agent/test_graph.py`
  - Verify graph injection writes grading metadata into the trace.
- Modify: `tests/api/test_sessions.py`
  - Verify app/service assembly passes the grader into the workflow and defaults to the LLM-backed adapter.
- Modify: `interviewer-note.md`
  - Log the grader-adapter boundary, fallback policy, and deployment default.

## Task 1: Add the deterministic grader adapter

**Files:**
- Create: `src/final_agent/agent/graders.py`
- Create: `tests/agent/test_graders.py`

- [ ] **Step 1: Write the failing deterministic grader test**

```python
from __future__ import annotations


def test_deterministic_grader_matches_expected_points():
    from final_agent.agent.graders import DeterministicGrader

    grade = DeterministicGrader().grade(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds and testing.",
        materials=[],
    )

    assert grade.score == 1.0
    assert grade.covered_points == ["automation", "testing"]
    assert grade.missed_points == []
    assert grade.feedback == "Covered all expected points."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graders.py::test_deterministic_grader_matches_expected_points -v`

Expected: FAIL because `final_agent.agent.graders` does not exist yet.

- [ ] **Step 3: Write the minimal deterministic implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from final_agent.agent.models import GradeResult


@dataclass
class GradeEvaluationMeta:
    implementation: str
    fallback_reason: str = ""


class DeterministicGrader:
    implementation = "deterministic"

    def grade(
        self,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> GradeResult:
        normalized = learner_answer.lower()
        covered = [point for point in expected_points if point.lower() in normalized]
        missed = [point for point in expected_points if point not in covered]
        score = len(covered) / len(expected_points) if expected_points else 0.0
        return GradeResult(
            score=score,
            covered_points=covered,
            missed_points=missed,
            feedback="Covered all expected points." if not missed else f"Review: {', '.join(missed)}",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graders.py::test_deterministic_grader_matches_expected_points -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/graders.py tests/agent/test_graders.py
git commit -m "feat: add deterministic grader adapter"
```

## Task 2: Add the LLM grader and deterministic fallback

**Files:**
- Modify: `src/final_agent/agent/graders.py`
- Modify: `tests/agent/test_graders.py`

- [ ] **Step 1: Write the failing LLM success test**

```python
def test_llm_grader_validates_json(monkeypatch):
    from final_agent.agent.graders import LlmGrader

    monkeypatch.setattr(
        "final_agent.agent.graders.llm_generate",
        lambda messages, settings=None, model=None, temperature=None, max_tokens=None: (
            '{"score":0.5,"covered_points":["automation"],"missed_points":["testing"],"feedback":"Mention testing too."}'
        ),
    )

    grade, meta = LlmGrader().grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert grade.score == 0.5
    assert grade.covered_points == ["automation"]
    assert grade.missed_points == ["testing"]
    assert meta.implementation == "llm"
    assert meta.fallback_reason == ""
```

- [ ] **Step 2: Write the failing fallback test**

```python
def test_llm_grader_falls_back_to_deterministic_on_bad_json(monkeypatch):
    from final_agent.agent.graders import LlmGrader

    monkeypatch.setattr(
        "final_agent.agent.graders.llm_generate",
        lambda messages, settings=None, model=None, temperature=None, max_tokens=None: "not-json",
    )

    grade, meta = LlmGrader().grade_with_meta(
        "What is CI?",
        ["automation", "testing"],
        "CI uses automation for builds.",
        materials=[],
    )

    assert grade.score == 0.5
    assert grade.covered_points == ["automation"]
    assert meta.implementation == "deterministic-fallback"
    assert "json" in meta.fallback_reason.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graders.py::test_llm_grader_validates_json tests/agent/test_graders.py::test_llm_grader_falls_back_to_deterministic_on_bad_json -v`

Expected: FAIL because the LLM grader behavior is not implemented yet.

- [ ] **Step 4: Implement `LlmGrader` and fallback**

```python
import json

from final_agent.generation.llm_client import generate as llm_generate
from final_agent.settings import load_settings


class LlmGrader:
    implementation = "llm"

    def __init__(self, fallback: DeterministicGrader | None = None):
        self.fallback = fallback or DeterministicGrader()

    def grade_with_meta(
        self,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> tuple[GradeResult, GradeEvaluationMeta]:
        prompt = (
            "Return only JSON for grading with keys "
            '"score", "covered_points", "missed_points", "feedback". '
            f"Question: {question}\n"
            f"Expected points: {expected_points}\n"
            f"Learner answer: {learner_answer}\n"
            f"Materials: {materials or []}"
        )
        try:
            raw = llm_generate([{"role": "user", "content": prompt}], settings=load_settings())
            data = json.loads(raw)
            grade = GradeResult.model_validate(data)
            return grade, GradeEvaluationMeta(implementation="llm")
        except json.JSONDecodeError as exc:
            grade = self.fallback.grade(question, expected_points, learner_answer, materials=materials)
            return grade, GradeEvaluationMeta(
                implementation="deterministic-fallback",
                fallback_reason=f"JSON decode error: {exc}"[:120],
            )
        except Exception as exc:
            grade = self.fallback.grade(question, expected_points, learner_answer, materials=materials)
            return grade, GradeEvaluationMeta(
                implementation="deterministic-fallback",
                fallback_reason=str(exc)[:120],
            )

    def grade(
        self,
        question: str,
        expected_points: list[str],
        learner_answer: str,
        *,
        materials: list[Any] | None = None,
    ) -> GradeResult:
        grade, _ = self.grade_with_meta(
            question,
            expected_points,
            learner_answer,
            materials=materials,
        )
        return grade
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graders.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/agent/graders.py tests/agent/test_graders.py
git commit -m "feat: add llm-backed grader fallback"
```

## Task 3: Delegate `grade_answer` through the injected grader

**Files:**
- Modify: `src/final_agent/agent/tools.py`
- Modify: `tests/agent/test_tools.py`

- [ ] **Step 1: Write the failing delegation test**

```python
def test_grade_answer_delegates_to_injected_grader():
    from final_agent.agent.models import GradeResult
    from final_agent.agent.tools import grade_answer

    class FakeGrader:
        def grade(self, question, expected_points, learner_answer, *, materials=None):
            return GradeResult(
                score=0.25,
                covered_points=["adapter"],
                missed_points=["testing"],
                feedback="Injected grade",
            )

    result = grade_answer(
        "What is CI?",
        ["automation", "testing"],
        "adapter",
        grader=FakeGrader(),
        materials=[],
    )

    assert result.ok is True
    assert result.value.score == 0.25
    assert result.value.feedback == "Injected grade"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/agent/test_tools.py::test_grade_answer_delegates_to_injected_grader -v`

Expected: FAIL because `grade_answer` does not accept `grader` or `materials`.

- [ ] **Step 3: Implement the delegation**

```python
from final_agent.agent.graders import DeterministicGrader


def grade_answer(
    question: str,
    expected_points: list[str],
    learner_answer: str,
    *,
    grader=None,
    materials=None,
) -> ToolResult:
    selected_grader = grader or DeterministicGrader()
    return run_tool(
        lambda: selected_grader.grade(
            question,
            expected_points,
            learner_answer,
            materials=materials or [],
        )
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n final-agent python -m pytest tests/agent/test_tools.py::test_grade_answer_delegates_to_injected_grader -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/tools.py tests/agent/test_tools.py
git commit -m "refactor: delegate grading through adapter"
```

## Task 4: Inject the grader into the workflow and preserve observability

**Files:**
- Modify: `src/final_agent/agent/graph.py`
- Modify: `tests/agent/test_graph.py`

- [ ] **Step 1: Write the failing graph injection test**

```python
def test_graph_uses_injected_grader():
    from final_agent.agent.graph import run_study_turn
    from final_agent.agent.models import AgentState, GradeResult, QuizQuestion

    class FakeGrader:
        def grade_with_meta(self, question, expected_points, learner_answer, *, materials=None):
            return (
                GradeResult(
                    score=0.75,
                    covered_points=["automation"],
                    missed_points=[],
                    feedback="Injected grade",
                ),
                type("Meta", (), {"implementation": "llm", "fallback_reason": ""})(),
            )

        def grade(self, question, expected_points, learner_answer, *, materials=None):
            raise AssertionError("graph should use grade_with_meta for observability")

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        status="waiting_for_answer",
        quiz=QuizQuestion(
            question_id="q1",
            topic="review CI",
            prompt="What is CI?",
            expected_points=["automation"],
        ),
        learner_answer="automation matters",
    )

    updated = run_study_turn(state, grader=FakeGrader())

    assert updated.grade is not None
    assert updated.grade.feedback == "Injected grade"
    assert "impl=llm" in updated.tool_trace[-2].input_summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graph.py::test_graph_uses_injected_grader -v`

Expected: FAIL because `run_study_turn` does not accept `grader`.

- [ ] **Step 3: Implement workflow injection and trace observability**

```python
from final_agent.agent.graders import DeterministicGrader


def run_study_turn(state: AgentState, repository=None, quiz_generator=None, grader=None) -> AgentState:
    grader = grader or DeterministicGrader()

    if state.status == "waiting_for_answer":
        if not state.learner_answer:
            return state
        if state.quiz is None:
            state.quiz = QuizQuestion(
                question_id=f"quiz-{uuid4().hex[:8]}",
                topic=state.learning_goal,
                prompt=f"Explain {state.learning_goal}",
                expected_points=[state.learning_goal.lower()],
            )
        grade_meta = None
        if hasattr(grader, "grade_with_meta"):
            grade_result = run_tool(
                lambda: grader.grade_with_meta(
                    state.quiz.prompt,
                    state.quiz.expected_points,
                    state.learner_answer,
                    materials=[],
                )
            )
            if grade_result.ok:
                state.grade, grade_meta = grade_result.value
        else:
            grade_result = grade_answer(
                state.quiz.prompt,
                state.quiz.expected_points,
                state.learner_answer,
                grader=grader,
                materials=[],
            )
            if grade_result.ok:
                state.grade = grade_result.value
        _append_trace(
            state,
            "grade_answer",
            grade_result.ok,
            grade_result.elapsed_ms,
            grade_meta.fallback_reason if grade_meta else grade_result.error,
            input_summary=(
                f"{state.quiz.topic[:60]} | impl={grade_meta.implementation}"
                if grade_meta
                else state.learning_goal[:80]
            ),
        )
        if not grade_result.ok:
            state.status = "failed"
            return state
        if state.grade is None:
            state.grade = grade_result.value
        if repository is not None:
            repository.save_attempt(state.session_id, state.quiz, state.learner_answer, state.grade)
        mastery_result = update_mastery(state.session_id, state.quiz.topic, state.grade.score, repository)
        _append_trace(state, "update_mastery", mastery_result.ok, mastery_result.elapsed_ms, mastery_result.error)
        if not mastery_result.ok:
            state.status = "failed"
            return state
        state.next_action = choose_learning_action(state.grade.score)
        state.status = "completed"
        return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graph.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/graph.py tests/agent/test_graph.py
git commit -m "feat: inject grader into study workflow"
```

## Task 5: Assemble the default grader in the API layer

**Files:**
- Modify: `src/final_agent/api/app.py`
- Modify: `tests/api/test_sessions.py`
- Modify: `interviewer-note.md`

- [ ] **Step 1: Write the failing default-assembly test**

```python
def test_agent_service_defaults_to_llm_grader(tmp_path):
    from final_agent.agent.graders import DeterministicGrader, LlmGrader
    from final_agent.api.app import AgentService
    from final_agent.memory.repository import MemoryRepository

    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"))

    assert isinstance(service.grader, LlmGrader)
    assert isinstance(service.grader.fallback, DeterministicGrader)
```

- [ ] **Step 2: Write the failing pass-through test**

```python
def test_agent_service_passes_grader_to_workflow(tmp_path, monkeypatch):
    from final_agent.api.app import AgentService
    from final_agent.api.schemas import CreateSessionRequest
    from final_agent.memory.repository import MemoryRepository

    calls = {}

    def fake_run_study_turn(state, repository=None, quiz_generator=None, grader=None):
        calls["grader"] = grader
        state.status = "waiting_for_answer"
        return state

    monkeypatch.setattr("final_agent.api.app.run_study_turn", fake_run_study_turn)

    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"))
    service.create_session(CreateSessionRequest(learning_goal="review CI", course_ids=[]))

    assert calls["grader"] is service.grader
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `conda run -n final-agent python -m pytest tests/api/test_sessions.py::test_agent_service_defaults_to_llm_grader tests/api/test_sessions.py::test_agent_service_passes_grader_to_workflow -v`

Expected: FAIL because `AgentService` does not have grader assembly yet.

- [ ] **Step 4: Implement API assembly and log the decision**

```python
from final_agent.agent.graders import DeterministicGrader, LlmGrader
from final_agent.agent.quiz_generators import DeterministicQuizGenerator


class AgentService:
    def __init__(self, repository: MemoryRepository, quiz_generator=None, grader=None):
        self.repository = repository
        self.quiz_generator = quiz_generator or DeterministicQuizGenerator()
        self.grader = grader or LlmGrader(fallback=DeterministicGrader())

    def create_session(self, payload: CreateSessionRequest) -> SessionResponse:
        state = AgentState(session_id=uuid4().hex, learning_goal=payload.learning_goal, course_ids=payload.course_ids)
        state = run_study_turn(
            state,
            repository=self.repository,
            quiz_generator=self.quiz_generator,
            grader=self.grader,
        )
        self.repository.create_session(state)
        for trace in state.tool_trace:
            self.repository.append_trace(state.session_id, trace)
        return self._response(state)

    def send_message(self, session_id: str, message: str) -> SessionResponse:
        state = self.repository.get_session(session_id)
        if state.status != "waiting_for_answer":
            raise HTTPException(status_code=409, detail="Session is not waiting for an answer")
        state.learner_answer = message
        before = len(state.tool_trace)
        state = run_study_turn(
            state,
            repository=self.repository,
            quiz_generator=self.quiz_generator,
            grader=self.grader,
        )
        self.repository.save_session(state)
        for trace in state.tool_trace[before:]:
            self.repository.append_trace(state.session_id, trace)
        return self._response(state)
```

```python
def create_app(repository: MemoryRepository | None = None, quiz_generator=None, grader=None) -> FastAPI:
    app = FastAPI(title="final-agent Study Coach API")
    repo = repository or MemoryRepository()
    service = AgentService(repo, quiz_generator=quiz_generator, grader=grader)
    _warm_knowledge_cache()
```

Add an `interviewer-note.md` entry describing:

- why grading now mirrors the quiz adapter seam
- why the deployment default is `LlmGrader(fallback=DeterministicGrader())`
- why `materials` exists on the interface before grounded grading is wired in

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/api/test_sessions.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/api/app.py tests/api/test_sessions.py interviewer-note.md
git commit -m "feat: assemble grader at app startup"
```

## Task 6: Final focused verification

**Files:**
- Verify repository state only

- [ ] **Step 1: Run grader-focused tests**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graders.py tests/agent/test_tools.py tests/agent/test_graph.py tests/api/test_sessions.py -v`

Expected: PASS

- [ ] **Step 2: Run lint**

Run: `conda run -n final-agent python -m ruff check src tests`

Expected: PASS

- [ ] **Step 3: Run full regression if focused checks pass**

Run: `conda run -n final-agent python -m pytest --cov=final_agent --cov-report=term-missing`

Expected: PASS

- [ ] **Step 4: Check working tree**

Run: `git status --short`

Expected: only intentional changes from this task slice plus any unrelated pre-existing user changes.
