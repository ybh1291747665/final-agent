# Adaptive Study Coach Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `final-agent` into a tested, tool-using study coach that plans review workflows, grades learner answers, persists mastery, and adapts subsequent tasks.

**Architecture:** Keep the current ingestion, retrieval, generation, and Streamlit modules as the knowledge layer. Add typed tools, a LangGraph orchestrator, SQLite repositories, and a FastAPI service around those existing capabilities. Build the smallest complete learning loop before adding streaming or visual polish.

**Tech Stack:** Python 3.11, Pydantic 2, LangGraph, FastAPI, SQLite, pytest, existing ChromaDB/BM25/BGE/DeepSeek pipeline.

---

## File Map

- Modify `pyproject.toml`: add LangGraph, SQLAlchemy, HTTP test client, and coverage dependencies.
- Create `tests/`: baseline tests for current RAG behavior and all new Agent modules.
- Create `src/final_agent/evaluation/`: fixed evaluation cases, runners, and metrics.
- Create `src/final_agent/agent/models.py`: graph state and typed tool contracts.
- Create `src/final_agent/agent/tools.py`: adapters around existing retrieval and generation functions.
- Create `src/final_agent/agent/graph.py`: LangGraph nodes, routing, limits, and pause/resume.
- Create `src/final_agent/memory/models.py`: persisted session, mastery, quiz-attempt, and trace records.
- Create `src/final_agent/memory/repository.py`: SQLite persistence API.
- Create `src/final_agent/api/app.py`: FastAPI application and session endpoints.
- Modify `src/final_agent/ui/app.py`: consume the API and display plan, quiz, mastery, and tool trace.
- Modify `README.md`, `DESIGN.md`, and `interviewer-note.md`: document only shipped behavior and measured results.

## Week 1: Baseline, Code Understanding, and Evaluation

### Task 1: Establish a Reliable Test Harness

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: Add development dependencies**

Add `sqlalchemy>=2.0` to application dependencies. Add `pytest-cov>=5.0`, `httpx>=0.27`, and `ruff>=0.6` to the `dev` extra. Add pytest configuration with `testpaths = ["tests"]` and `addopts = "-q"`.

- [ ] **Step 2: Install the editable development environment**

Run: `pip install -e ".[dev]"`

Expected: installation exits with code 0 and `pytest --version` reports pytest 8 or newer.

- [ ] **Step 3: Write schema round-trip tests**

Create tests that instantiate `Chunk`, `ScoredChunk`, `GeneratedAnswer`, and `VerifiedAnswer`, serialize them with `model_dump_json()`, restore them with `model_validate_json()`, and assert identity of IDs, citations, page numbers, and flags.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_schemas.py -v`

Expected: all schema tests pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/conftest.py tests/test_schemas.py
git commit -m "test: establish project test harness"
```

### Task 2: Lock Down Current Retrieval Behavior

**Files:**
- Create: `tests/retrieval/test_hybrid_searcher.py`
- Create: `tests/retrieval/test_pipeline.py`
- Create: `tests/ingestion/test_chunker.py`

- [ ] **Step 1: Test RRF ranking without model downloads**

Monkeypatch `_dense_retrieve` and `_sparse_retrieve` to return deterministic `ScoredChunk` lists. Assert that a document ranked by both paths outranks a document returned by only one path and that results carry `source="rrf"`.

- [ ] **Step 2: Test course filtering and neighbor expansion**

Monkeypatch `hybrid_search`, `rerank`, `filter_results`, and `get_chunks_by_doc`. Assert that `deep_search()` includes adjacent chunks from the same document, excludes other courses, and returns no more than two chunks per heading path.

- [ ] **Step 3: Test page-aware chunking**

Use Markdown containing `<!-- page_start: 3 -->` and `<!-- page_start: 4 -->`. Assert that generated chunks retain the correct page number and heading path.

- [ ] **Step 4: Run the focused suite**

Run: `pytest tests/retrieval tests/ingestion -v`

Expected: deterministic tests pass without API keys, ChromaDB data, or model downloads.

- [ ] **Step 5: Commit**

```bash
git add tests/retrieval tests/ingestion
git commit -m "test: cover retrieval and chunking baseline"
```

### Task 3: Create the 30-Scenario Evaluation Baseline

**Files:**
- Create: `src/final_agent/evaluation/models.py`
- Create: `src/final_agent/evaluation/dataset.py`
- Create: `src/final_agent/evaluation/metrics.py`
- Create: `src/final_agent/evaluation/runner.py`
- Create: `tests/evaluation/test_metrics.py`

- [ ] **Step 1: Define evaluation models**

Create Pydantic models `EvaluationCase`, `EvaluationResult`, and `EvaluationSummary`. Each case stores `case_id`, `category`, `course_ids`, `user_input`, `expected_tools`, `required_citations`, and `expected_outcome`.

- [ ] **Step 2: Write metric tests first**

Test exact tool-selection accuracy, task completion rate, citation-grounding rate, mean latency, and grading agreement. Include empty-input behavior that returns zero rather than dividing by zero.

- [ ] **Step 3: Implement metric functions**

Implement pure functions in `metrics.py`; keep them independent from the LLM and database.

- [ ] **Step 4: Add 30 fixed scenarios**

Create 10 `retrieval`, 10 `tool_selection`, and 10 `adaptive_review` cases using imported course fixtures. Every case must have a human-written expected outcome.

- [ ] **Step 5: Add a baseline runner**

Run the current RAG pipeline for retrieval cases, record latency with `time.perf_counter()`, and write JSON results to `data/evaluation/baseline.json`.

- [ ] **Step 6: Execute the baseline**

Run: `python -m final_agent.evaluation.runner --suite baseline`

Expected: a 30-case JSON report is created; failures are recorded as results instead of terminating the run.

- [ ] **Step 7: Commit**

```bash
git add src/final_agent/evaluation tests/evaluation data/evaluation/baseline.json
git commit -m "feat: add reproducible evaluation baseline"
```

## Week 2: Typed Tools and LangGraph Orchestration

### Task 4: Define Agent State and Tool Contracts

**Files:**
- Modify: `pyproject.toml`
- Create: `src/final_agent/agent/__init__.py`
- Create: `src/final_agent/agent/models.py`
- Create: `tests/agent/test_models.py`

- [ ] **Step 1: Add LangGraph**

Add `langgraph>=0.2,<1.0` to application dependencies, then run `pip install -e ".[dev]"`.

- [ ] **Step 2: Write model validation tests**

Test that `AgentState` requires `session_id` and `learning_goal`, limits `tool_call_count` to 0-6, and supports statuses `planning`, `running`, `waiting_for_answer`, `completed`, and `failed`.

- [ ] **Step 3: Implement models**

Define `StudyPlanStep`, `QuizQuestion`, `GradeResult`, `MasteryUpdate`, `ToolTraceEntry`, `ToolResult`, and `AgentState`. Use Pydantic models at module boundaries and a `TypedDict` projection only where LangGraph requires it.

Use this public contract:

```python
from typing import Literal
from pydantic import BaseModel, Field

AgentStatus = Literal["planning", "running", "waiting_for_answer", "completed", "failed"]

class StudyPlanStep(BaseModel):
    step_id: str
    objective: str
    tool_name: str
    completed: bool = False

class QuizQuestion(BaseModel):
    question_id: str
    topic: str
    prompt: str
    expected_points: list[str]
    difficulty: Literal["easy", "medium", "hard"] = "medium"

class GradeResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    covered_points: list[str] = Field(default_factory=list)
    missed_points: list[str] = Field(default_factory=list)
    feedback: str

class ToolTraceEntry(BaseModel):
    tool_name: str
    input_summary: str
    ok: bool
    elapsed_ms: int
    error: str = ""

class AgentState(BaseModel):
    session_id: str
    learning_goal: str
    course_ids: list[str] = Field(default_factory=list)
    plan: list[StudyPlanStep] = Field(default_factory=list)
    current_step: int = 0
    quiz: QuizQuestion | None = None
    learner_answer: str = ""
    grade: GradeResult | None = None
    tool_trace: list[ToolTraceEntry] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0, le=6)
    status: AgentStatus = "planning"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/agent/test_models.py -v`

Expected: validation and serialization tests pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/final_agent/agent tests/agent/test_models.py
git commit -m "feat: define study agent contracts"
```

### Task 5: Wrap Existing Capabilities as Testable Tools

**Files:**
- Create: `src/final_agent/agent/tools.py`
- Create: `tests/agent/test_tools.py`

- [ ] **Step 1: Write tool-adapter tests**

Monkeypatch existing functions and verify these adapters:

- `search_course_material(query, course_ids, top_k)` calls `retrieval.pipeline.search`.
- `summarize_course(doc_id, mode)` calls `generation.summarizer.summarize_document`.
- `generate_quiz(topic, course_ids, count)` retrieves context and calls `generate_exam`.
- `grade_answer(question, expected_points, learner_answer)` returns structured correctness, feedback, and covered points.
- `get_learning_profile(session_id)` and `update_mastery(...)` call repository interfaces rather than raw SQL.

- [ ] **Step 2: Implement the adapters**

Return `ToolResult(ok, value, error, elapsed_ms)` from every tool. Catch expected exceptions, log them, and return `ok=False`; do not leak API keys or full prompts into errors.

Use one wrapper for timing and error conversion:

```python
from collections.abc import Callable
from time import perf_counter
from typing import Any

class ToolResult(BaseModel):
    ok: bool
    value: Any = None
    error: str = ""
    elapsed_ms: int = 0

def run_tool(operation: Callable[[], Any]) -> ToolResult:
    started = perf_counter()
    try:
        return ToolResult(
            ok=True,
            value=operation(),
            elapsed_ms=int((perf_counter() - started) * 1000),
        )
    except (RuntimeError, ValueError, TimeoutError) as exc:
        return ToolResult(
            ok=False,
            error=str(exc),
            elapsed_ms=int((perf_counter() - started) * 1000),
        )
```

- [ ] **Step 3: Add tool registry metadata**

Expose a registry mapping tool names to descriptions and Pydantic input schemas so the planner cannot invent unsupported tools.

- [ ] **Step 4: Run tests**

Run: `pytest tests/agent/test_tools.py -v`

Expected: tool success and error paths pass with no network calls.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/tools.py tests/agent/test_tools.py
git commit -m "feat: expose RAG capabilities as typed tools"
```

### Task 6: Build the Bounded Agent Graph

**Files:**
- Create: `src/final_agent/agent/graph.py`
- Create: `src/final_agent/agent/prompts.py`
- Create: `tests/agent/test_graph.py`

- [ ] **Step 1: Write graph-routing tests**

Use a fake planner and fake tools. Cover: plan creation, valid tool execution, unsupported-tool rejection, six-call limit, tool failure, pause before learner answer, resume after answer, and successful completion.

- [ ] **Step 2: Implement graph nodes**

Create nodes `understand_goal`, `create_plan`, `select_tool`, `execute_tool`, `request_answer`, `grade_answer`, `update_mastery`, `choose_next_step`, and `finish`.

Build the graph with explicit edges:

```python
from langgraph.graph import END, StateGraph

def build_graph(checkpointer):
    graph = StateGraph(dict)
    graph.add_node("understand_goal", understand_goal)
    graph.add_node("create_plan", create_plan)
    graph.add_node("select_tool", select_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("request_answer", request_answer)
    graph.add_node("grade_answer", grade_answer)
    graph.add_node("update_mastery", update_mastery)
    graph.add_node("choose_next_step", choose_next_step)
    graph.add_node("finish", finish)
    graph.set_entry_point("understand_goal")
    graph.add_edge("understand_goal", "create_plan")
    graph.add_edge("create_plan", "select_tool")
    graph.add_conditional_edges("select_tool", route_selected_tool)
    graph.add_conditional_edges("execute_tool", route_after_tool)
    graph.add_edge("request_answer", "grade_answer")
    graph.add_edge("grade_answer", "update_mastery")
    graph.add_edge("update_mastery", "choose_next_step")
    graph.add_conditional_edges("choose_next_step", route_next_step)
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer, interrupt_before=["grade_answer"])
```

- [ ] **Step 3: Implement deterministic routing**

Route from state fields, not free-form model text. Validate planned tool names against the registry. Set `status="failed"` when the call limit is reached or a non-retryable tool error occurs.

- [ ] **Step 4: Add pause and resume**

Compile the graph with a checkpointer. Interrupt before `grade_answer` when `learner_answer` is empty; resume the same session after the answer arrives.

- [ ] **Step 5: Run tests**

Run: `pytest tests/agent/test_graph.py -v`

Expected: all paths terminate, pause, or fail explicitly; no test can enter an unbounded loop.

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/agent/graph.py src/final_agent/agent/prompts.py tests/agent/test_graph.py
git commit -m "feat: add bounded LangGraph study workflow"
```

## Week 3: Persistent Memory and Adaptive Review

### Task 7: Implement SQLite Learner Memory

**Files:**
- Create: `src/final_agent/memory/__init__.py`
- Create: `src/final_agent/memory/models.py`
- Create: `src/final_agent/memory/repository.py`
- Create: `tests/memory/test_repository.py`

- [ ] **Step 1: Write repository tests against a temporary database**

Test session creation, retrieval, quiz-attempt storage, mastery upsert, trace append, transaction rollback, and isolation between two session IDs.

- [ ] **Step 2: Define the schema**

Create tables `sessions`, `mastery`, `quiz_attempts`, and `tool_traces`. Use unique `(session_id, topic)` mastery keys and UTC timestamps.

Use these minimum columns:

```text
sessions(id PK, learning_goal, status, state_json, created_at, updated_at)
mastery(session_id FK, topic, score, attempts, updated_at, UNIQUE(session_id, topic))
quiz_attempts(id PK, session_id FK, question_id, topic, answer, score, feedback, created_at)
tool_traces(id PK, session_id FK, sequence_no, tool_name, input_summary, ok, elapsed_ms, error, created_at)
```

- [ ] **Step 3: Implement the repository interface**

Provide `create_session`, `get_session`, `save_attempt`, `get_mastery`, `upsert_mastery`, `append_trace`, and `list_trace`. Keep SQL inside this module.

- [ ] **Step 4: Run tests**

Run: `pytest tests/memory/test_repository.py -v`

Expected: all repository tests pass on a fresh temporary SQLite file.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/memory tests/memory
git commit -m "feat: persist learner mastery and agent traces"
```

### Task 8: Add Transparent Mastery Adaptation

**Files:**
- Create: `src/final_agent/agent/mastery.py`
- Create: `tests/agent/test_mastery.py`
- Modify: `src/final_agent/agent/graph.py`

- [ ] **Step 1: Write mastery-rule tests**

Assert these rules:

- Score below 0.4 selects `re_explain` and an easier question.
- Score from 0.4 through 0.7 selects `practice_variant`.
- Score above 0.7 selects `advance_topic`.
- New mastery equals `0.7 * previous + 0.3 * latest_score`, clamped to 0-1.

- [ ] **Step 2: Implement pure mastery functions**

Create `update_mastery_score(previous, latest)` and `choose_learning_action(score)`. Do not call the LLM in these functions.

```python
from typing import Literal

LearningAction = Literal["re_explain", "practice_variant", "advance_topic"]

def update_mastery_score(previous: float, latest: float) -> float:
    return min(1.0, max(0.0, 0.7 * previous + 0.3 * latest))

def choose_learning_action(score: float) -> LearningAction:
    if score < 0.4:
        return "re_explain"
    if score <= 0.7:
        return "practice_variant"
    return "advance_topic"
```

- [ ] **Step 3: Connect graph adaptation**

After grading, persist the attempt and mastery update, then route according to `choose_learning_action`.

- [ ] **Step 4: Run graph and mastery tests**

Run: `pytest tests/agent/test_mastery.py tests/agent/test_graph.py -v`

Expected: low, medium, and high mastery paths select different next actions.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/agent/mastery.py src/final_agent/agent/graph.py tests/agent
git commit -m "feat: adapt study workflow from learner mastery"
```

## Week 4: API, UI, Evaluation, and Portfolio Evidence

### Task 9: Expose Agent Sessions Through FastAPI

**Files:**
- Create: `src/final_agent/api/__init__.py`
- Create: `src/final_agent/api/app.py`
- Create: `src/final_agent/api/schemas.py`
- Create: `tests/api/test_sessions.py`
- Modify: `src/final_agent/main.py`

- [ ] **Step 1: Write API contract tests**

Using FastAPI `TestClient`, cover:

- `POST /sessions` creates a session from a learning goal.
- `POST /sessions/{id}/messages` advances or resumes the graph.
- `GET /sessions/{id}` returns status and current plan.
- `GET /sessions/{id}/mastery` returns topic mastery.
- `GET /sessions/{id}/trace` returns ordered tool calls.
- Unknown sessions return HTTP 404; invalid payloads return HTTP 422.

- [ ] **Step 2: Implement request and response schemas**

Define explicit Pydantic API models; do not expose database rows or internal graph dictionaries directly.

```python
class CreateSessionRequest(BaseModel):
    learning_goal: str = Field(min_length=3, max_length=500)
    course_ids: list[str] = Field(default_factory=list)

class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)

class SessionResponse(BaseModel):
    session_id: str
    status: AgentStatus
    plan: list[StudyPlanStep]
    quiz: QuizQuestion | None = None
    grade: GradeResult | None = None
```

- [ ] **Step 3: Implement endpoints with dependency injection**

Inject the graph runner and repository so tests use fakes. Return HTTP 503 for temporary model or retrieval failures and HTTP 409 when a message conflicts with the current session state.

```python
@app.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(payload: CreateSessionRequest, service: AgentService = Depends(get_service)):
    return service.create_session(payload)

@app.post("/sessions/{session_id}/messages", response_model=SessionResponse)
def send_message(session_id: str, payload: SendMessageRequest, service: AgentService = Depends(get_service)):
    return service.send_message(session_id, payload.message)
```

- [ ] **Step 4: Add CLI command**

Add `final-agent api --host 127.0.0.1 --port 8000` to launch Uvicorn.

- [ ] **Step 5: Run tests**

Run: `pytest tests/api/test_sessions.py -v`

Expected: all endpoint contracts pass without external APIs.

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/api src/final_agent/main.py tests/api
git commit -m "feat: expose study agent session API"
```

### Task 10: Add the Study Coach UI

**Files:**
- Modify: `src/final_agent/ui/app.py`
- Create: `src/final_agent/ui/agent_client.py`
- Create: `tests/ui/test_agent_client.py`

- [ ] **Step 1: Test the API client**

Mock HTTP responses for session creation, message sending, mastery retrieval, and trace retrieval. Assert timeouts and non-2xx responses become user-readable exceptions.

- [ ] **Step 2: Implement the client**

Keep all HTTP calls in `agent_client.py`; set connect and read timeouts explicitly.

- [ ] **Step 3: Add Study Coach mode**

Add a mode that displays the learning goal, generated plan, current question, answer input, grading feedback, mastery bars, and expandable tool trace. Preserve the existing RAG modes.

- [ ] **Step 4: Verify manually**

Run: `final-agent api` and `final-agent ui` in separate terminals.

Expected: a user can create a goal, receive a quiz, submit an answer, see feedback, and observe mastery change without refreshing the page manually.

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/ui tests/ui
git commit -m "feat: add adaptive study coach interface"
```

### Task 11: Run the Final Evaluation and Publish Evidence

**Files:**
- Modify: `src/final_agent/evaluation/runner.py`
- Create: `data/evaluation/agent-final.json`
- Modify: `README.md`
- Modify: `DESIGN.md`
- Modify: `interviewer-note.md`

- [ ] **Step 1: Extend the runner to Agent scenarios**

Run each fixed scenario with a clean session, capture selected tools, terminal status, citations, grade, and elapsed time, and continue after individual failures.

- [ ] **Step 2: Run all automated checks**

Run:

```bash
ruff check src tests
pytest --cov=final_agent --cov-report=term-missing
```

Expected: lint exits 0; tests report zero failures. Record coverage but do not invent a target after seeing the result.

- [ ] **Step 3: Run the final 30-case evaluation**

Run: `python -m final_agent.evaluation.runner --suite agent-final`

Expected: `data/evaluation/agent-final.json` contains all 30 results and aggregate metrics.

- [ ] **Step 4: Update documentation with measured values**

Replace obsolete MinerU-first descriptions, document the Agent workflow, include exact evaluation methodology, publish measured metrics, and list known limitations.

- [ ] **Step 5: Create portfolio assets**

Record a 90-second demonstration showing goal creation, tool calls, quiz pause, answer grading, mastery update, and adaptive next step. Add one architecture diagram and one anonymized tool trace to README.

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/evaluation data/evaluation README.md DESIGN.md interviewer-note.md
git commit -m "docs: publish study coach evaluation and architecture"
```

## Daily Learning Routine

- 60-90 minutes: Python fundamentals, typing, exceptions, pytest, and the framework used that day.
- 90-120 minutes: implement one planned slice personally, starting from its failing test.
- 30 minutes: explain the modified call path aloud without reading notes.
- 15 minutes: record one design decision, one bug, and one unresolved question in `interviewer-note.md`.

## Resume Upgrade Gate

Keep the current title **RAG-Powered Study Assistant** until Tasks 4-11 are complete and the final evaluation report exists. Then rename it **Adaptive Study Coach Agent** and use measured bullets only:

- Built a LangGraph-based study agent that plans review workflows and invokes retrieval, summarization, quiz-generation, and grading tools.
- Implemented persistent learner memory to track mastery, identify weak topics, and adapt subsequent review tasks.
- Exposed session workflows through FastAPI and achieved the measured tool-selection, grounding, and task-completion results in `agent-final.json`.
