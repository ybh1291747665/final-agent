# Quiz Generator Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an injectable quiz-generator adapter layer with deterministic and LLM-backed implementations while preserving the current `QuizQuestion` contract and outward Study Coach behavior.

**Architecture:** Add a dedicated `quiz_generators` module containing deterministic and LLM-backed implementations plus a small factory. Inject the selected generator from app/service into the workflow, keep fallback inside the LLM adapter, and preserve existing API/UI payloads.

**Tech Stack:** Python, Pydantic, OpenAI-compatible LLM client, FastAPI, pytest

---

## File Map

- Create: `src/final_agent/agent/quiz_generators.py`
  - Define the generator protocol, deterministic implementation, LLM implementation, and a small factory/helper.
- Modify: `src/final_agent/agent/tools.py`
  - Delegate quiz generation to an injected generator instead of hard-coded regex logic.
- Modify: `src/final_agent/agent/graph.py`
  - Accept an injected quiz generator and carry lightweight observability into the trace.
- Modify: `src/final_agent/api/app.py`
  - Assemble and pass the default quiz generator from app/service.
- Test: `tests/agent/test_quiz_generators.py`
  - Verify deterministic behavior, LLM success, and fallback behavior.
- Modify: `tests/agent/test_graph.py`
  - Verify graph injection writes the produced quiz into state.
- Modify: `tests/agent/test_tools.py`
  - Verify `generate_quiz` delegates to the provided generator.
- Modify: `interviewer-note.md`
  - Log the adapter boundary and fallback decision.

## Task 1: Add the quiz generator adapter module

**Files:**
- Create: `src/final_agent/agent/quiz_generators.py`
- Test: `tests/agent/test_quiz_generators.py`

- [ ] **Step 1: Write the failing deterministic adapter test**

```python
def test_deterministic_quiz_generator_returns_quiz_question():
    from final_agent.agent.quiz_generators import DeterministicQuizGenerator

    quiz = DeterministicQuizGenerator().generate("review configuration management", [], 1)

    assert quiz.topic == "review configuration management"
    assert quiz.expected_points == ["review", "configuration", "management"]
    assert quiz.difficulty == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/agent/test_quiz_generators.py::test_deterministic_quiz_generator_returns_quiz_question -v`

Expected: FAIL because `quiz_generators.py` does not exist yet.

- [ ] **Step 3: Write minimal deterministic implementation**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from final_agent.agent.models import QuizQuestion


@dataclass
class QuizGenerationMeta:
    implementation: str
    fallback_reason: str = ""


class DeterministicQuizGenerator:
    implementation = "deterministic"

    def generate(self, topic: str, course_ids: list[str] | None = None, count: int = 1) -> QuizQuestion:
        points = [word for word in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", topic.lower()) if len(word) > 2]
        expected_points = points[:3] or [topic.lower()]
        return QuizQuestion(
            question_id=f"quiz-{abs(hash((topic, count))) % 100000}",
            topic=topic,
            prompt=f"Explain {topic} and mention: {', '.join(expected_points)}.",
            expected_points=expected_points,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n final-agent python -m pytest tests/agent/test_quiz_generators.py::test_deterministic_quiz_generator_returns_quiz_question -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/quiz_generators.py tests/agent/test_quiz_generators.py
git commit -m "feat: add quiz generator adapter module"
```

## Task 2: Add LLM generation and deterministic fallback

**Files:**
- Modify: `src/final_agent/agent/quiz_generators.py`
- Test: `tests/agent/test_quiz_generators.py`

- [ ] **Step 1: Write the failing LLM success test**

```python
def test_llm_quiz_generator_validates_json(monkeypatch):
    from final_agent.agent.quiz_generators import LlmQuizGenerator

    monkeypatch.setattr(
        "final_agent.agent.quiz_generators.llm_generate",
        lambda messages, settings=None, model=None, temperature=None, max_tokens=None: (
            '{"question_id":"quiz-1","topic":"review CI","prompt":"What is CI?","expected_points":["automation"],"difficulty":"easy"}'
        ),
    )

    quiz, meta = LlmQuizGenerator().generate_with_meta("review CI", [], 1)

    assert quiz.prompt == "What is CI?"
    assert quiz.expected_points == ["automation"]
    assert meta.implementation == "llm"
    assert meta.fallback_reason == ""
```

- [ ] **Step 2: Write the failing fallback test**

```python
def test_llm_quiz_generator_falls_back_to_deterministic_on_bad_json(monkeypatch):
    from final_agent.agent.quiz_generators import LlmQuizGenerator

    monkeypatch.setattr(
        "final_agent.agent.quiz_generators.llm_generate",
        lambda messages, settings=None, model=None, temperature=None, max_tokens=None: "not-json",
    )

    quiz, meta = LlmQuizGenerator().generate_with_meta("review CI", [], 1)

    assert quiz.topic == "review CI"
    assert meta.implementation == "deterministic-fallback"
    assert "json" in meta.fallback_reason.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `conda run -n final-agent python -m pytest tests/agent/test_quiz_generators.py::test_llm_quiz_generator_validates_json tests/agent/test_quiz_generators.py::test_llm_quiz_generator_falls_back_to_deterministic_on_bad_json -v`

Expected: FAIL because the LLM adapter behavior is not implemented yet.

- [ ] **Step 4: Implement `LlmQuizGenerator` and fallback**

```python
import json

from final_agent.generation.llm_client import generate as llm_generate
from final_agent.settings import load_settings


class LlmQuizGenerator:
    implementation = "llm"

    def __init__(self, fallback: DeterministicQuizGenerator | None = None):
        self.fallback = fallback or DeterministicQuizGenerator()

    def generate_with_meta(self, topic: str, course_ids: list[str] | None = None, count: int = 1) -> tuple[QuizQuestion, QuizGenerationMeta]:
        prompt = (
            "Return only JSON for a quiz question with keys "
            '"question_id", "topic", "prompt", "expected_points", "difficulty". '
            f"Goal: {topic}"
        )
        try:
            raw = llm_generate([{"role": "user", "content": prompt}], settings=load_settings())
            data = json.loads(raw)
            quiz = QuizQuestion.model_validate(data)
            return quiz, QuizGenerationMeta(implementation="llm")
        except Exception as exc:
            quiz = self.fallback.generate(topic, course_ids, count)
            return quiz, QuizGenerationMeta(
                implementation="deterministic-fallback",
                fallback_reason=str(exc)[:120],
            )

    def generate(self, topic: str, course_ids: list[str] | None = None, count: int = 1) -> QuizQuestion:
        quiz, _ = self.generate_with_meta(topic, course_ids, count)
        return quiz
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/agent/test_quiz_generators.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/agent/quiz_generators.py tests/agent/test_quiz_generators.py
git commit -m "feat: add llm-backed quiz generator fallback"
```

## Task 3: Delegate `generate_quiz` through the injected generator

**Files:**
- Modify: `src/final_agent/agent/tools.py`
- Modify: `tests/agent/test_tools.py`

- [ ] **Step 1: Write the failing delegation test**

```python
def test_generate_quiz_delegates_to_injected_generator():
    from final_agent.agent.tools import generate_quiz
    from final_agent.agent.models import QuizQuestion

    class FakeGenerator:
        def generate(self, topic, course_ids=None, count=1):
            return QuizQuestion(
                question_id="quiz-x",
                topic=topic,
                prompt="Injected prompt",
                expected_points=["adapter"],
                difficulty="hard",
            )

    result = generate_quiz("review CI", ["course-a"], 1, quiz_generator=FakeGenerator())

    assert result.ok is True
    assert result.value.prompt == "Injected prompt"
    assert result.value.difficulty == "hard"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/agent/test_tools.py::test_generate_quiz_delegates_to_injected_generator -v`

Expected: FAIL because `generate_quiz` does not accept `quiz_generator`.

- [ ] **Step 3: Implement the delegation**

```python
from final_agent.agent.quiz_generators import DeterministicQuizGenerator


def generate_quiz(
    topic: str,
    course_ids: list[str] | None = None,
    count: int = 1,
    *,
    quiz_generator=None,
) -> ToolResult:
    generator = quiz_generator or DeterministicQuizGenerator()
    return run_tool(lambda: generator.generate(topic, course_ids or [], count))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n final-agent python -m pytest tests/agent/test_tools.py::test_generate_quiz_delegates_to_injected_generator -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/tools.py tests/agent/test_tools.py
git commit -m "refactor: delegate quiz generation through adapter"
```

## Task 4: Inject the generator into the workflow and preserve observability

**Files:**
- Modify: `src/final_agent/agent/graph.py`
- Modify: `tests/agent/test_graph.py`

- [ ] **Step 1: Write the failing graph injection test**

```python
def test_graph_uses_injected_quiz_generator():
    from final_agent.agent.graph import run_study_turn
    from final_agent.agent.models import AgentState, QuizQuestion

    class FakeGenerator:
        def generate_with_meta(self, topic, course_ids=None, count=1):
            return (
                QuizQuestion(
                    question_id="quiz-injected",
                    topic=topic,
                    prompt="Injected prompt",
                    expected_points=["adapter"],
                    difficulty="hard",
                ),
                type("Meta", (), {"implementation": "llm", "fallback_reason": ""})(),
            )

        def generate(self, topic, course_ids=None, count=1):
            raise AssertionError("graph should use generate_with_meta for observability")

    state = run_study_turn(AgentState(session_id="s1", learning_goal="review CI"), quiz_generator=FakeGenerator())

    assert state.quiz is not None
    assert state.quiz.prompt == "Injected prompt"
    assert "impl=llm" in state.tool_trace[-1].input_summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graph.py::test_graph_uses_injected_quiz_generator -v`

Expected: FAIL because `run_study_turn` does not accept `quiz_generator`.

- [ ] **Step 3: Implement workflow injection and trace observability**

```python
from final_agent.agent.quiz_generators import DeterministicQuizGenerator


def run_study_turn(state: AgentState, repository=None, quiz_generator=None) -> AgentState:
    quiz_generator = quiz_generator or DeterministicQuizGenerator()
    ...
    quiz_result = run_tool(lambda: quiz_generator.generate(state.learning_goal, state.course_ids, 1))
    quiz_meta = None
    if hasattr(quiz_generator, "generate_with_meta"):
        quiz_result = run_tool(lambda: quiz_generator.generate_with_meta(state.learning_goal, state.course_ids, 1))
        if quiz_result.ok:
            state.quiz, quiz_meta = quiz_result.value
    ...
    _append_trace(
        state,
        "generate_quiz",
        quiz_result.ok,
        quiz_result.elapsed_ms,
        quiz_meta.fallback_reason if quiz_meta else quiz_result.error,
    )
    if quiz_meta:
        state.tool_trace[-1].input_summary = f"{state.learning_goal[:60]} | impl={quiz_meta.implementation}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/agent/test_graph.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/graph.py tests/agent/test_graph.py
git commit -m "feat: inject quiz generator into study workflow"
```

## Task 5: Assemble the default generator in the API layer

**Files:**
- Modify: `src/final_agent/api/app.py`
- Modify: `interviewer-note.md`

- [ ] **Step 1: Write the failing assembly test**

```python
def test_agent_service_passes_quiz_generator_to_workflow(tmp_path, monkeypatch):
    from final_agent.api.app import AgentService
    from final_agent.api.schemas import CreateSessionRequest
    from final_agent.memory.repository import MemoryRepository
    from final_agent.agent.models import AgentState

    calls = {}

    def fake_run_study_turn(state, repository=None, quiz_generator=None):
        calls["quiz_generator"] = quiz_generator
        state.status = "waiting_for_answer"
        return state

    monkeypatch.setattr("final_agent.api.app.run_study_turn", fake_run_study_turn)

    service = AgentService(MemoryRepository(tmp_path / "api.sqlite"), quiz_generator=object())
    service.create_session(CreateSessionRequest(learning_goal="review CI", course_ids=[]))

    assert calls["quiz_generator"] is service.quiz_generator
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n final-agent python -m pytest tests/api/test_sessions.py::test_agent_service_passes_quiz_generator_to_workflow -v`

Expected: FAIL because `AgentService` does not accept `quiz_generator`.

- [ ] **Step 3: Implement API assembly and logging note**

```python
from final_agent.agent.quiz_generators import DeterministicQuizGenerator


class AgentService:
    def __init__(self, repository: MemoryRepository, quiz_generator=None):
        self.repository = repository
        self.quiz_generator = quiz_generator or DeterministicQuizGenerator()

    def create_session(self, payload: CreateSessionRequest) -> SessionResponse:
        state = AgentState(session_id=uuid4().hex, learning_goal=payload.learning_goal, course_ids=payload.course_ids)
        state = run_study_turn(state, repository=self.repository, quiz_generator=self.quiz_generator)
        ...
```

```python
def create_app(repository: MemoryRepository | None = None, quiz_generator=None) -> FastAPI:
    ...
    service = AgentService(repo, quiz_generator=quiz_generator)
```

Add an `interviewer-note.md` entry describing:

- why explicit injection was chosen over global default state
- why fallback remains internal to the adapter in this phase

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n final-agent python -m pytest tests/api/test_sessions.py::test_agent_service_passes_quiz_generator_to_workflow tests/api/test_sessions.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/api/app.py tests/api/test_sessions.py interviewer-note.md
git commit -m "feat: assemble quiz generator at app startup"
```

## Task 6: Final focused verification

**Files:**
- Verify repository state only

- [ ] **Step 1: Run adapter-focused tests**

Run: `conda run -n final-agent python -m pytest tests/agent/test_quiz_generators.py tests/agent/test_tools.py tests/agent/test_graph.py tests/api/test_sessions.py -v`

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
