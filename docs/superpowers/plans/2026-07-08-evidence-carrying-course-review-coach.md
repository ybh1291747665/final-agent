# Evidence-Carrying Course Review Coach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next AI/RAG-focused stage of the Course Review Coach: each single-question review turn carries top-3 course evidence from retrieval into quiz generation, grading, critic checks, API responses, UI evidence display, and readable RAG citations.

**Architecture:** Keep the existing fixed sequential multi-agent orchestration. Add compact `EvidenceSnapshot` records to `AgentState` and API responses, keep full chunk text transient inside the orchestrator for quiz/grading, and update UI surfaces to display file-name/page citations instead of raw chunk IDs. Redis, background workers, autonomous planning, parallel agents, and new API namespaces are intentionally excluded.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, SQLAlchemy Core, SQLite, Streamlit, pytest, httpx.

---

## Scope Decisions From Discussion

- Product framing: **Course Review Coach**, not exam proctor, generic quiz app, or agent platform.
- Entry model: **Learning goal + optional course scope**.
- Review shape: **one turn, one question, one answer, one grade, one next action**.
- Evidence rule: **Top-3 Evidence Set**.
- Persistence/API rule: `AgentState` and API store compact evidence snapshots only.
- Runtime rule: full chunk text may be passed transiently to quiz/grader tools.
- Feedback rule: learner-facing feedback should explain coverage and gaps using course evidence, without raw chunk IDs in the main prose.
- Evidence inspection rule: Evidence panel can show technical source details.
- Citation display rule: file name + page number first, e.g. `software-engineering.pdf，第 12 页`.
- Redis: not part of this plan. It belongs to a later deployment/worker plan only if background ingest, realtime timeline, rate limiting, or multi-worker execution becomes necessary.

---

## File Structure

- Modify `src/final_agent/agent/models.py`
  - Add `EvidenceSnapshot`.
  - Add `AgentState.evidence_snapshots`.
- Create `src/final_agent/agent/evidence.py`
  - Convert retrieved `ScoredChunk` objects into top-3 compact snapshots.
  - Build transient material dictionaries for quiz/grading.
  - Format evidence summaries for trace output.
- Modify `src/final_agent/agent/tools.py`
  - Allow `GenerateQuizInput` and `generate_quiz()` to receive transient materials.
  - Keep `GradeAnswerInput.materials` as transient full-text inputs.
- Modify `src/final_agent/agent/quiz_generators.py`
  - Make deterministic quiz generation evidence-aware while preserving backward compatibility.
- Modify `src/final_agent/agent/graders.py`
  - Make deterministic grading feedback evidence-aware while preserving score behavior.
- Modify `src/final_agent/agent/orchestrator.py`
  - Capture retrieval results.
  - Store compact evidence snapshots on state.
  - Pass full materials to quiz and grader.
  - Pass actual evidence count to critic.
- Modify `src/final_agent/api/schemas.py`
  - Expose `evidence_snapshots` on `SessionResponse`.
- Modify `src/final_agent/api/app.py`
  - Include `state.evidence_snapshots` in responses.
- Modify `src/final_agent/ui/study_coach_view.py`
  - Format evidence snapshots for Study Coach output.
- Modify `src/final_agent/ui/app.py`
  - Show Study Coach evidence snapshots.
  - Keep Ask/Deep QA readable citations wired through UI helpers.
- Modify `src/final_agent/ui/workspace.py`
  - Add or keep readable citation helpers.
  - Build chunk registries with file/page metadata.
- Modify `tests/agent/*`, `tests/api/*`, `tests/ui/*`, `tests/docs/*`
  - Add deterministic evidence-carrying tests.
- Modify `docs/e2e-acceptance.md`
  - Add checks for evidence-carrying Study Coach and readable citations.

---

### Task 1: Evidence Snapshot Model

**Files:**
- Modify: `src/final_agent/agent/models.py`
- Test: `tests/agent/test_evidence_snapshots.py`

- [ ] **Step 1: Write the failing test**

Create `tests/agent/test_evidence_snapshots.py`:

```python
from __future__ import annotations


def test_agent_state_carries_compact_evidence_snapshots():
    from final_agent.agent.models import AgentState, EvidenceSnapshot

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        evidence_snapshots=[
            EvidenceSnapshot(
                chunk_id="aaaabbbb1111",
                doc_id="doc-a",
                source_path="E:/courses/software-engineering.pdf",
                page_num=12,
                heading="Continuous Integration",
                summary="CI runs automated builds and tests.",
                score=0.91,
                retrieval_source="rrf",
            )
        ],
    )

    assert state.evidence_snapshots[0].chunk_id == "aaaabbbb1111"
    assert state.evidence_snapshots[0].page_num == 12
    assert state.evidence_snapshots[0].summary == "CI runs automated builds and tests."


def test_evidence_snapshot_does_not_require_full_chunk_text():
    from final_agent.agent.models import EvidenceSnapshot

    snapshot = EvidenceSnapshot(
        chunk_id="aaaabbbb1111",
        doc_id="doc-a",
        source_path="E:/courses/software-engineering.pdf",
        page_num=12,
        heading="Continuous Integration",
        summary="CI runs automated builds and tests.",
        score=0.91,
        retrieval_source="rrf",
    )

    assert "text" not in snapshot.model_dump()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_evidence_snapshots.py -q
```

Expected: FAIL because `EvidenceSnapshot` and `AgentState.evidence_snapshots` do not exist.

- [ ] **Step 3: Implement the model**

Modify `src/final_agent/agent/models.py`.

Add after `CriticWarning`:

```python
class EvidenceSnapshot(BaseModel):
    chunk_id: str
    doc_id: str = ""
    source_path: str = ""
    page_num: int | None = None
    heading: str = ""
    summary: str = ""
    score: float = 0.0
    retrieval_source: str = ""
```

Add to `AgentState`:

```python
    evidence_snapshots: list[EvidenceSnapshot] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_evidence_snapshots.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/models.py tests/agent/test_evidence_snapshots.py
git commit -m "feat: add compact evidence snapshots"
```

---

### Task 2: Evidence Conversion Helpers

**Files:**
- Create: `src/final_agent/agent/evidence.py`
- Test: `tests/agent/test_evidence_helpers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_evidence_helpers.py`:

```python
from __future__ import annotations


def test_evidence_snapshots_keep_top_three_and_compact_fields():
    from final_agent.agent.evidence import build_evidence_snapshots
    from final_agent.schemas import Chunk, ScoredChunk

    results = [
        ScoredChunk(
            chunk=Chunk(
                chunk_id=f"chunk-{idx}",
                doc_id="doc-a",
                text=f"Evidence text {idx} " * 20,
                heading_path=["CI", f"Part {idx}"],
                page_num=idx,
                metadata={"source_path": "E:/courses/software-engineering.pdf"},
            ),
            score=1.0 - idx * 0.1,
            source="rrf",
        )
        for idx in range(1, 5)
    ]

    snapshots = build_evidence_snapshots(results, limit=3)

    assert [snapshot.chunk_id for snapshot in snapshots] == ["chunk-1", "chunk-2", "chunk-3"]
    assert snapshots[0].heading == "CI > Part 1"
    assert snapshots[0].source_path == "E:/courses/software-engineering.pdf"
    assert snapshots[0].page_num == 1
    assert len(snapshots[0].summary) <= 220
    assert "text" not in snapshots[0].model_dump()


def test_materials_keep_full_text_for_transient_tool_inputs():
    from final_agent.agent.evidence import build_transient_materials
    from final_agent.schemas import Chunk, ScoredChunk

    results = [
        ScoredChunk(
            chunk=Chunk(
                chunk_id="aaaabbbb1111",
                doc_id="doc-a",
                text="CI runs automated builds and tests.",
                heading_path=["CI"],
                page_num=7,
                metadata={"source_path": "E:/courses/software-engineering.pdf"},
            ),
            score=0.91,
            source="rrf",
        )
    ]

    materials = build_transient_materials(results, limit=3)

    assert materials == [
        {
            "chunk_id": "aaaabbbb1111",
            "doc_id": "doc-a",
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 7,
            "heading": "CI",
            "text": "CI runs automated builds and tests.",
            "score": 0.91,
            "retrieval_source": "rrf",
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_evidence_helpers.py -q
```

Expected: FAIL because `final_agent.agent.evidence` does not exist.

- [ ] **Step 3: Implement evidence helpers**

Create `src/final_agent/agent/evidence.py`:

```python
from __future__ import annotations

from collections.abc import Sequence

from final_agent.agent.models import EvidenceSnapshot
from final_agent.schemas import ScoredChunk


def _heading(chunk) -> str:
    return " > ".join(chunk.heading_path) if chunk.heading_path else ""


def _source_path(chunk) -> str:
    return str(chunk.metadata.get("source_path", "") or "")


def _summary(text: str, max_chars: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def build_evidence_snapshots(results: Sequence[ScoredChunk], *, limit: int = 3) -> list[EvidenceSnapshot]:
    snapshots: list[EvidenceSnapshot] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        snapshots.append(
            EvidenceSnapshot(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                source_path=_source_path(chunk),
                page_num=chunk.page_num,
                heading=_heading(chunk),
                summary=_summary(chunk.text),
                score=result.score,
                retrieval_source=result.source,
            )
        )
    return snapshots


def build_transient_materials(results: Sequence[ScoredChunk], *, limit: int = 3) -> list[dict]:
    materials: list[dict] = []
    for result in list(results)[:limit]:
        chunk = result.chunk
        materials.append(
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "source_path": _source_path(chunk),
                "page_num": chunk.page_num,
                "heading": _heading(chunk),
                "text": chunk.text,
                "score": result.score,
                "retrieval_source": result.source,
            }
        )
    return materials


def summarize_evidence_for_trace(snapshots: Sequence[EvidenceSnapshot]) -> str:
    if not snapshots:
        return "0 evidence snapshots"
    return f"{len(snapshots)} evidence snapshots"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_evidence_helpers.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/evidence.py tests/agent/test_evidence_helpers.py
git commit -m "feat: build compact evidence snapshots"
```

---

### Task 3: Evidence-Aware Quiz Tool

**Files:**
- Modify: `src/final_agent/agent/tools.py`
- Modify: `src/final_agent/agent/quiz_generators.py`
- Test: `tests/agent/test_evidence_aware_quiz.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_evidence_aware_quiz.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_evidence_aware_quiz.py -q
```

Expected: FAIL because `GenerateQuizInput.materials` and `generate_quiz(..., materials=...)` are not implemented.

- [ ] **Step 3: Implement evidence-aware quiz generation**

Modify `src/final_agent/agent/tools.py`.

Change `GenerateQuizInput`:

```python
class GenerateQuizInput(BaseModel):
    topic: str
    course_ids: list[str] = Field(default_factory=list)
    count: int = 1
    materials: list[Any] = Field(default_factory=list)
```

Change `generate_quiz`:

```python
def generate_quiz(
    topic: str,
    course_ids: list[str] | None = None,
    count: int = 1,
    *,
    quiz_generator=None,
    materials: list[Any] | None = None,
) -> ToolResult:
    generator = quiz_generator or DeterministicQuizGenerator()
    selected_materials = [] if materials is None else materials
    if hasattr(generator, "generate_with_evidence"):
        return run_tool(lambda: generator.generate_with_evidence(topic, course_ids or [], count, materials=selected_materials))
    return run_tool(lambda: generator.generate(topic, course_ids or [], count))
```

Modify `src/final_agent/agent/quiz_generators.py`.

Add imports if needed:

```python
from typing import Any
```

Add to `DeterministicQuizGenerator`:

```python
    def generate_with_evidence(
        self,
        topic: str,
        course_ids: list[str] | None = None,
        count: int = 1,
        *,
        materials: list[Any] | None = None,
    ) -> QuizQuestion:
        materials = materials or []
        if not materials:
            return self.generate(topic, course_ids, count)
        first = materials[0]
        text = str(first.get("text", "")) if isinstance(first, dict) else str(first)
        heading = str(first.get("heading", "")) if isinstance(first, dict) else ""
        points = [word for word in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text.lower()) if len(word) > 4]
        expected_points = list(dict.fromkeys(points[:3])) or [topic.lower()]
        evidence_label = heading or topic
        return QuizQuestion(
            question_id=f"quiz-{abs(hash((topic, text[:80], count))) % 100000}",
            topic=topic,
            prompt=f"Using the course evidence from {evidence_label}, explain {topic} and mention: {', '.join(expected_points)}.",
            expected_points=expected_points,
        )
```

Modify `build_default_tool_registry()` in `src/final_agent/agent/tool_registry.py` so `generate_quiz` passes materials:

```python
tools.generate_quiz(
    payload.topic,
    payload.course_ids,
    payload.count,
    quiz_generator=quiz_generator,
    materials=payload.materials,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_evidence_aware_quiz.py tests/agent/test_tool_registry_defaults.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/tools.py src/final_agent/agent/tool_registry.py src/final_agent/agent/quiz_generators.py tests/agent/test_evidence_aware_quiz.py
git commit -m "feat: generate quizzes from retrieved evidence"
```

---

### Task 4: Evidence-Based Grading Feedback

**Files:**
- Modify: `src/final_agent/agent/graders.py`
- Test: `tests/agent/test_evidence_based_grading.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_evidence_based_grading.py`:

```python
from __future__ import annotations


def test_deterministic_grader_feedback_mentions_missing_evidence_point():
    from final_agent.agent.graders import DeterministicGrader

    grade = DeterministicGrader().grade(
        "Explain CI.",
        ["automated", "tests"],
        "CI means automated builds.",
        materials=[
            {
                "heading": "Continuous Integration",
                "text": "Continuous integration runs automated builds and tests after each change.",
            }
        ],
    )

    assert grade.score == 0.5
    assert grade.covered_points == ["automated"]
    assert grade.missed_points == ["tests"]
    assert "course evidence" in grade.feedback
    assert "tests" in grade.feedback
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/agent/test_evidence_based_grading.py -q
```

Expected: FAIL because deterministic feedback does not mention course evidence.

- [ ] **Step 3: Implement evidence-based feedback**

Modify `DeterministicGrader.grade()` in `src/final_agent/agent/graders.py`.

Replace feedback creation with:

```python
        if not missed:
            feedback = "Covered all expected points from the course evidence."
        elif materials:
            evidence_hint = ""
            first = materials[0]
            if isinstance(first, dict):
                heading = str(first.get("heading", "")).strip()
                evidence_hint = f" in {heading}" if heading else ""
            feedback = f"Review course evidence{evidence_hint}: {', '.join(missed)}."
        else:
            feedback = f"Review: {', '.join(missed)}"
```

Then return:

```python
        return GradeResult(
            score=score,
            covered_points=covered,
            missed_points=missed,
            feedback=feedback,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_evidence_based_grading.py tests/agent/test_graders.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/graders.py tests/agent/test_evidence_based_grading.py
git commit -m "feat: ground grading feedback in evidence"
```

---

### Task 5: Orchestrator Carries Evidence Across Agents

**Files:**
- Modify: `src/final_agent/agent/orchestrator.py`
- Test: `tests/agent/test_orchestrator_evidence.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_orchestrator_evidence.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class EmptyInput(BaseModel):
    pass


def test_orchestrator_initial_turn_stores_top_three_evidence_snapshots():
    from final_agent.agent.models import AgentState, QuizQuestion, ToolCall
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec
    from final_agent.schemas import Chunk, ScoredChunk

    class SearchInput(BaseModel):
        query: str
        course_ids: list[str]
        top_k: int

    class QuizInput(BaseModel):
        topic: str
        course_ids: list[str]
        count: int
        materials: list[dict]

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="search_course_material",
            input_model=SearchInput,
            operation=lambda payload: [
                ScoredChunk(
                    chunk=Chunk(
                        chunk_id=f"chunk-{idx}",
                        doc_id="doc-a",
                        text=f"CI evidence text {idx}",
                        heading_path=["CI"],
                        page_num=idx,
                        metadata={"source_path": "E:/courses/software-engineering.pdf"},
                    ),
                    score=1.0 - idx * 0.1,
                    source="rrf",
                )
                for idx in range(1, 5)
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="generate_quiz",
            input_model=QuizInput,
            operation=lambda payload: QuizQuestion(
                question_id="q1",
                topic=payload.topic,
                prompt=f"Explain CI using {len(payload.materials)} evidence items.",
                expected_points=["evidence"],
            ),
        )
    )

    state = MultiAgentOrchestrator(registry=registry).run_turn(
        AgentState(session_id="s1", learning_goal="review CI")
    )

    assert state.status == "waiting_for_answer"
    assert len(state.evidence_snapshots) == 3
    assert [snapshot.page_num for snapshot in state.evidence_snapshots] == [1, 2, 3]
    assert state.quiz is not None
    assert "3 evidence items" in state.quiz.prompt
    assert state.agent_trace[1].output_summary == "3 evidence snapshots"


def test_orchestrator_answer_turn_passes_evidence_to_grader_and_critic():
    from final_agent.agent.models import AgentState, EvidenceSnapshot, GradeResult, MasteryRecord, QuizQuestion
    from final_agent.agent.orchestrator import MultiAgentOrchestrator
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    calls: dict[str, object] = {}

    class GradeInput(BaseModel):
        question: str
        expected_points: list[str]
        learner_answer: str
        materials: list[dict]

    class MasteryInput(BaseModel):
        session_id: str
        topic: str
        score: float

    class EvidenceInput(BaseModel):
        quiz_prompt: str
        evidence_count: int

    class ConsistencyInput(BaseModel):
        score: float
        next_action: str

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="grade_answer",
            input_model=GradeInput,
            operation=lambda payload: (
                calls.setdefault("materials", payload.materials)
                or GradeResult(score=1.0, covered_points=["automation"], missed_points=[], feedback="Evidence-based feedback.")
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="update_mastery",
            input_model=MasteryInput,
            operation=lambda payload: MasteryRecord(topic=payload.topic, score=payload.score, attempts=1),
        )
    )
    registry.register(
        ToolSpec(
            name="verify_evidence",
            input_model=EvidenceInput,
            operation=lambda payload: calls.setdefault("evidence_count", payload.evidence_count) or [],
        )
    )
    registry.register(
        ToolSpec(
            name="verify_grade_consistency",
            input_model=ConsistencyInput,
            operation=lambda payload: [],
        )
    )

    state = AgentState(
        session_id="s1",
        learning_goal="review CI",
        quiz=QuizQuestion(question_id="q1", topic="review CI", prompt="Explain CI.", expected_points=["automation"]),
        learner_answer="automation",
        status="waiting_for_answer",
        evidence_snapshots=[
            EvidenceSnapshot(
                chunk_id="aaaabbbb1111",
                doc_id="doc-a",
                source_path="E:/courses/software-engineering.pdf",
                page_num=4,
                heading="CI",
                summary="CI runs automation.",
                score=0.9,
                retrieval_source="rrf",
            )
        ],
    )

    state = MultiAgentOrchestrator(registry=registry).run_turn(state)

    assert state.status == "completed"
    assert calls["materials"] == [
        {
            "chunk_id": "aaaabbbb1111",
            "doc_id": "doc-a",
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 4,
            "heading": "CI",
            "text": "CI runs automation.",
            "score": 0.9,
            "retrieval_source": "rrf",
        }
    ]
    assert calls["evidence_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_orchestrator_evidence.py -q
```

Expected: FAIL because orchestrator does not store snapshots, pass materials to quiz/grader, or use actual evidence count.

- [ ] **Step 3: Implement evidence-carrying orchestration**

Modify `src/final_agent/agent/orchestrator.py`.

Add imports:

```python
from final_agent.agent.evidence import build_evidence_snapshots, build_transient_materials, summarize_evidence_for_trace
```

Add helper method inside `MultiAgentOrchestrator`:

```python
    def _materials_from_snapshots(self, state: AgentState) -> list[dict]:
        return [
            {
                "chunk_id": snapshot.chunk_id,
                "doc_id": snapshot.doc_id,
                "source_path": snapshot.source_path,
                "page_num": snapshot.page_num,
                "heading": snapshot.heading,
                "text": snapshot.summary,
                "score": snapshot.score,
                "retrieval_source": snapshot.retrieval_source,
            }
            for snapshot in state.evidence_snapshots
        ]
```

In the initial turn after retrieval:

```python
            materials: list[dict] = []
            if retrieval.ok:
                state.evidence_snapshots = build_evidence_snapshots(retrieval.value, limit=3)
                materials = build_transient_materials(retrieval.value, limit=3)
                if len(state.agent_trace) >= 2:
                    state.agent_trace[-1].output_summary = summarize_evidence_for_trace(state.evidence_snapshots)
```

Change the quiz call arguments:

```python
                ToolCall(
                    name="generate_quiz",
                    arguments={
                        "topic": state.learning_goal,
                        "course_ids": state.course_ids,
                        "count": 1,
                        "materials": materials,
                    },
                ),
```

In the answer turn, change grade `materials`:

```python
                        "materials": self._materials_from_snapshots(state),
```

Change critic evidence call:

```python
                ToolCall(
                    name="verify_evidence",
                    arguments={
                        "quiz_prompt": state.quiz.prompt,
                        "evidence_count": len(state.evidence_snapshots),
                    },
                ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/agent/test_orchestrator_evidence.py tests/agent/test_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/orchestrator.py tests/agent/test_orchestrator_evidence.py
git commit -m "feat: carry evidence through study coach agents"
```

---

### Task 6: API Exposes Evidence Snapshots

**Files:**
- Modify: `src/final_agent/api/schemas.py`
- Modify: `src/final_agent/api/app.py`
- Test: `tests/api/test_study_coach_evidence.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/api/test_study_coach_evidence.py`:

```python
from __future__ import annotations

import httpx
import pytest


@pytest.mark.anyio
async def test_session_response_exposes_evidence_snapshots(tmp_path):
    from final_agent.agent.models import AgentState, EvidenceSnapshot, QuizQuestion
    from final_agent.api.app import create_app
    from final_agent.memory.repository import MemoryRepository

    class FakeOrchestrator:
        def run_turn(self, state: AgentState) -> AgentState:
            state.status = "waiting_for_answer"
            state.quiz = QuizQuestion(
                question_id="q1",
                topic=state.learning_goal,
                prompt="Explain CI.",
                expected_points=["automation"],
            )
            state.evidence_snapshots = [
                EvidenceSnapshot(
                    chunk_id="aaaabbbb1111",
                    doc_id="doc-a",
                    source_path="E:/courses/software-engineering.pdf",
                    page_num=12,
                    heading="CI",
                    summary="CI runs automated tests.",
                    score=0.91,
                    retrieval_source="rrf",
                )
            ]
            return state

    app = create_app(
        repository=MemoryRepository(tmp_path / "api.sqlite"),
        orchestrator=FakeOrchestrator(),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/sessions", json={"learning_goal": "review CI", "course_ids": []})

    assert response.status_code == 201
    body = response.json()
    assert body["evidence_snapshots"] == [
        {
            "chunk_id": "aaaabbbb1111",
            "doc_id": "doc-a",
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 12,
            "heading": "CI",
            "summary": "CI runs automated tests.",
            "score": 0.91,
            "retrieval_source": "rrf",
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_study_coach_evidence.py -q
```

Expected: FAIL because `SessionResponse` does not expose `evidence_snapshots`.

- [ ] **Step 3: Extend API schema and response**

Modify `src/final_agent/api/schemas.py` import:

```python
from final_agent.agent.models import AgentStatus, AgentToolTraceEntry, CriticWarning, EvidenceSnapshot, GradeResult, QuizQuestion, StudyPlanStep, ToolTraceEntry
```

Add to `SessionResponse`:

```python
    evidence_snapshots: list[EvidenceSnapshot] = Field(default_factory=list)
```

Modify `src/final_agent/api/app.py` in `_response()`:

```python
            evidence_snapshots=state.evidence_snapshots,
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/api/test_study_coach_evidence.py tests/api/test_multi_agent_sessions.py tests/api/test_sessions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/api/schemas.py src/final_agent/api/app.py tests/api/test_study_coach_evidence.py
git commit -m "feat: expose study coach evidence snapshots"
```

---

### Task 7: Study Coach UI Evidence Formatting

**Files:**
- Modify: `src/final_agent/ui/study_coach_view.py`
- Modify: `src/final_agent/ui/app.py`
- Test: `tests/ui/test_study_coach_rendering.py`

- [ ] **Step 1: Write the failing UI tests**

Append to `tests/ui/test_study_coach_rendering.py`:

```python
def test_format_evidence_snapshots_prefers_file_name_and_page():
    from final_agent.ui.study_coach_view import format_evidence_snapshots

    snapshots = [
        {
            "chunk_id": "aaaabbbb1111",
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 12,
            "heading": "CI",
            "summary": "CI runs automated tests.",
            "score": 0.91,
        }
    ]

    assert format_evidence_snapshots(snapshots) == [
        "**software-engineering.pdf，第 12 页** · CI · score=0.91\nCI runs automated tests."
    ]


def test_format_evidence_snapshots_handles_empty_state():
    from final_agent.ui.study_coach_view import format_evidence_snapshots

    assert format_evidence_snapshots([]) == ["No evidence snapshots yet."]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/ui/test_study_coach_rendering.py::test_format_evidence_snapshots_prefers_file_name_and_page tests/ui/test_study_coach_rendering.py::test_format_evidence_snapshots_handles_empty_state -q
```

Expected: FAIL because `format_evidence_snapshots` does not exist.

- [ ] **Step 3: Implement formatter and UI expander**

Modify `src/final_agent/ui/study_coach_view.py`.

Add imports:

```python
from pathlib import Path
```

Add helper:

```python
def _evidence_label(snapshot: dict) -> str:
    source_path = str(snapshot.get("source_path", "") or "")
    file_name = Path(source_path).name if source_path else str(snapshot.get("doc_id", "") or "")
    page_num = snapshot.get("page_num")
    if file_name and page_num:
        return f"{file_name}，第 {int(page_num)} 页"
    if file_name:
        return file_name
    if page_num:
        return f"第 {int(page_num)} 页"
    return f"chunk {str(snapshot.get('chunk_id', ''))[:8]}"
```

Add formatter:

```python
def format_evidence_snapshots(snapshots: list[dict]) -> list[str]:
    if not snapshots:
        return ["No evidence snapshots yet."]
    lines: list[str] = []
    for snapshot in snapshots:
        label = _evidence_label(snapshot)
        heading = snapshot.get("heading", "")
        score = float(snapshot.get("score", 0.0))
        summary = snapshot.get("summary", "")
        middle = f" · {heading}" if heading else ""
        lines.append(f"**{label}**{middle} · score={score:.2f}\n{summary}")
    return lines
```

Modify `src/final_agent/ui/app.py` import:

```python
from final_agent.ui.study_coach_view import format_agent_timeline, format_critic_warnings, format_evidence_snapshots, format_study_coach_summary, format_trace_lines
```

In `_run_study_coach_turn()`, after rendering `content`:

```python
        with st.expander("Study Coach evidence", expanded=False):
            for line in format_evidence_snapshots(response.get("evidence_snapshots", [])):
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
git commit -m "feat: show study coach evidence snapshots"
```

---

### Task 8: Readable RAG Citations For Ask And Deep QA

**Files:**
- Modify: `src/final_agent/ui/workspace.py`
- Modify: `src/final_agent/ui/app.py`
- Test: `tests/ui/test_workspace.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_workspace.py`:

```python
def test_format_citation_label_prefers_file_name_and_page():
    from final_agent.ui.workspace import format_citation_label

    assert format_citation_label(
        "aaaabbbb1111",
        {
            "source_path": "E:/courses/software-engineering.pdf",
            "doc_id": "doc-a",
            "page_num": 12,
        },
    ) == "software-engineering.pdf，第 12 页"


def test_format_citation_label_falls_back_when_page_or_file_is_missing():
    from final_agent.ui.workspace import format_citation_label

    assert format_citation_label("aaaabbbb1111", {"source_path": "E:/courses/software-engineering.pdf"}) == (
        "software-engineering.pdf"
    )
    assert format_citation_label("aaaabbbb1111", {"doc_id": "doc-a", "page_num": 3}) == "doc-a，第 3 页"
    assert format_citation_label("aaaabbbb1111", {}) == "chunk aaaabbbb"


def test_replace_citation_labels_hides_raw_chunk_ids():
    from final_agent.ui.workspace import replace_citation_labels

    text = "CI runs automated tests [aaaabbbb1111]. It catches integration issues [ccccdddd2222]."
    registry = {
        "aaaabbbb1111": {
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 12,
        },
        "ccccdddd2222": {
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 13,
        },
    }

    assert replace_citation_labels(text, registry) == (
        "CI runs automated tests [software-engineering.pdf，第 12 页]. "
        "It catches integration issues [software-engineering.pdf，第 13 页]."
    )


def test_build_chunk_registry_adds_readable_citation_metadata():
    from final_agent.schemas import Chunk, ScoredChunk
    from final_agent.ui.workspace import build_chunk_registry

    registry = build_chunk_registry(
        [
            ScoredChunk(
                chunk=Chunk(
                    chunk_id="aaaabbbb1111",
                    doc_id="doc-a",
                    text="CI runs tests.",
                    heading_path=["CI"],
                    page_num=7,
                ),
                score=0.91,
                source="rrf",
            )
        ],
        {"doc-a": {"source_path": "E:/courses/software-engineering.pdf"}},
    )

    assert registry["aaaabbbb1111"]["citation_label"] == "software-engineering.pdf，第 7 页"
    assert registry["aaaabbbb1111"]["source_path"] == "E:/courses/software-engineering.pdf"
    assert registry["aaaabbbb1111"]["page_num"] == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/ui/test_workspace.py::test_format_citation_label_prefers_file_name_and_page tests/ui/test_workspace.py::test_format_citation_label_falls_back_when_page_or_file_is_missing tests/ui/test_workspace.py::test_replace_citation_labels_hides_raw_chunk_ids tests/ui/test_workspace.py::test_build_chunk_registry_adds_readable_citation_metadata -q
```

Expected: FAIL because readable citation helpers do not exist.

- [ ] **Step 3: Implement readable citation helpers**

Modify `src/final_agent/ui/workspace.py`.

Add imports:

```python
from pathlib import Path
import re

from final_agent.schemas import ScoredChunk
```

Add near the top:

```python
_CITATION_TOKEN_RE = re.compile(r"\[([A-Za-z0-9_-]{3,64})\]")
```

Add helpers:

```python
def format_citation_label(chunk_id: str, entry: dict) -> str:
    source_path = str(entry.get("source_path") or "").strip()
    file_name = str(entry.get("file_name") or "").strip()
    doc_id = str(entry.get("doc_id") or "").strip()
    page_num = entry.get("page_num")

    if not file_name and source_path:
        file_name = Path(source_path).name
    base = file_name or doc_id

    try:
        page = int(page_num) if page_num not in (None, "") else 0
    except (TypeError, ValueError):
        page = 0

    if base and page > 0:
        return f"{base}，第 {page} 页"
    if base:
        return base
    if page > 0:
        return f"第 {page} 页"
    return f"chunk {chunk_id[:8]}"


def replace_citation_labels(text: str, chunk_registry: dict) -> str:
    def _replace(match: re.Match[str]) -> str:
        chunk_id = match.group(1)
        entry = chunk_registry.get(chunk_id)
        if not entry:
            return match.group(0)
        return f"[{format_citation_label(chunk_id, entry)}]"

    return _CITATION_TOKEN_RE.sub(_replace, text)


def build_chunk_registry(results: Sequence[ScoredChunk], documents: dict | None = None) -> dict:
    documents = documents or {}
    registry = {}
    for result in results:
        chunk = result.chunk
        doc_meta = documents.get(chunk.doc_id, {})
        source_path = str(doc_meta.get("source_path", "") or chunk.metadata.get("source_path", ""))
        file_name = Path(source_path).name if source_path else ""
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else "(top)"
        entry = {
            "heading": heading,
            "text": chunk.text,
            "score": result.score,
            "source": result.source,
            "doc_id": chunk.doc_id,
            "source_path": source_path,
            "file_name": file_name,
            "page_num": chunk.page_num,
        }
        entry["citation_label"] = format_citation_label(chunk.chunk_id, entry)
        registry[chunk.chunk_id] = entry
    return registry
```

- [ ] **Step 4: Wire Streamlit display**

Modify `src/final_agent/ui/app.py`.

Import:

```python
from final_agent.ui.workspace import (
    build_chunk_registry,
    format_citation_label,
    replace_citation_labels,
    ...
)
```

Replace `_build_registry()` body:

```python
def _build_registry(results):
    """Build chunk_registry dict from ScoredChunk list."""
    docs = list_documents(settings=st.session_state.settings)
    return build_chunk_registry(results, docs)
```

In QA mode:

```python
                    if ans and ans.answer:
                        chunk_registry = _build_registry(results)
                        display_answer = replace_citation_labels(ans.answer, chunk_registry)
                        st.markdown(display_answer)
                        flag_data = _run_hallucination_check(ans, results, cur)
                        _show_hallucination(flag_data, chunk_registry)
                        _show_citations(ans, chunk_registry)

                        app_state._add_message(
                            "assistant",
                            content=display_answer,
                            flags=flag_data,
                            citations=ans.citations,
                            chunk_registry=chunk_registry,
                        )
```

In Deep QA mode:

```python
                    if ans and ans.answer:
                        chunk_registry = _build_registry(results)
                        display_answer = replace_citation_labels(ans.answer, chunk_registry)
                        st.markdown(display_answer)
                        _show_citations(ans, chunk_registry)
                        app_state._add_message(
                            "assistant",
                            content=display_answer,
                            citations=ans.citations,
                            chunk_registry=chunk_registry,
                        )
```

Update citation, evidence, and validation display call sites so they use:

```python
label = format_citation_label(cid, chunk_registry.get(cid, {}))
```

and render `[{label}]` instead of `[{cid[:8]}]`.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/ui/test_workspace.py tests/ui/test_study_coach_rendering.py -q
python -m compileall -q src/final_agent/ui tests/ui
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/ui/workspace.py src/final_agent/ui/app.py tests/ui/test_workspace.py
git commit -m "feat: show readable rag citations"
```

---

### Task 9: Acceptance Docs For Evidence-Carrying Review

**Files:**
- Modify: `docs/e2e-acceptance.md`
- Modify: `tests/docs/test_acceptance_docs.py`

- [ ] **Step 1: Write the failing docs test**

Append to `tests/docs/test_acceptance_docs.py`:

```python
def test_acceptance_runbook_covers_evidence_carrying_review_turn():
    text = Path("docs/e2e-acceptance.md").read_text(encoding="utf-8")

    assert "Study Coach evidence" in text
    assert "top 3" in text
    assert "file name and page" in text
    assert "single-question review turn" in text
    assert "evidence-based feedback" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/docs/test_acceptance_docs.py::test_acceptance_runbook_covers_evidence_carrying_review_turn -q
```

Expected: FAIL because the runbook does not yet mention these checks.

- [ ] **Step 3: Update acceptance runbook**

Modify the Study Coach section of `docs/e2e-acceptance.md` so it includes:

```markdown
12. Open `Study Coach evidence`.
13. Confirm the turn shows at most top 3 evidence snapshots.
14. Confirm evidence entries show file name and page when page metadata is available.
15. Confirm the session remains a single-question review turn: one question, one answer, one grade, and one next action.
16. Confirm grading feedback is evidence-based feedback rather than generic encouragement.
```

Modify the Ask And Evidence section so it includes:

```markdown
10. Confirm RAG citations in the main answer use file name and page labels instead of raw chunk IDs when page metadata is available.
```

- [ ] **Step 4: Run docs tests**

Run:

```bash
pytest tests/docs/test_acceptance_docs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/e2e-acceptance.md tests/docs/test_acceptance_docs.py
git commit -m "docs: add evidence-carrying review acceptance checks"
```

---

### Task 10: Full Verification

**Files:**
- No production files.
- Test command only.

- [ ] **Step 1: Run targeted verification**

Run:

```bash
pytest tests/agent tests/api tests/ui tests/docs -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile verification**

Run:

```bash
python -m compileall -q src tests
```

Expected: command exits 0.

- [ ] **Step 3: Run full suite**

Run:

```bash
pytest -q
```

Expected: all tests pass. Existing third-party deprecation warnings may remain, but there must be no failures.

- [ ] **Step 4: Commit any verification-only docs if needed**

If no files changed during verification, do not create a commit.

If acceptance docs were corrected during verification, commit only those docs:

```bash
git add docs/e2e-acceptance.md tests/docs/test_acceptance_docs.py
git commit -m "docs: refine evidence acceptance checks"
```

---

## Self-Review Checklist

- Spec coverage: The plan covers Course Review Coach positioning, Learning Goal Entry, Single-Question Review Turn, top-3 evidence snapshots, evidence-based feedback, Citation-Aware Evidence Panel, readable file/page citations, API exposure, UI display, docs, and deterministic verification.
- Scope control: Redis, worker queues, realtime streaming, dynamic autonomous planning, parallel agent execution, exam mode, fixed question banks, and chapter-tree navigation are intentionally excluded.
- Type consistency: `EvidenceSnapshot`, `AgentState.evidence_snapshots`, `build_evidence_snapshots`, `build_transient_materials`, `GenerateQuizInput.materials`, `SessionResponse.evidence_snapshots`, and `format_evidence_snapshots` are introduced before later tasks use them.
- Backward compatibility: Existing `citations` remain chunk IDs internally for hallucination guard and lookup. Learner-facing citation labels are display-only.
- Test order: Every production behavior change has a failing test step before implementation.
