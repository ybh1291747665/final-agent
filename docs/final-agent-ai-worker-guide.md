# final-agent AI Worker Guide

> Use this file as the entry point for any AI assistant, coding agent, or human collaborator working on the `final-agent` improvement plan.
>
> This guide summarizes the phases, decision boundaries, metrics, and evidence gates. The detailed implementation checklist lives in:
>
> - `docs/superpowers/plans/2026-06-13-adaptive-study-coach-agent.md`
> - `docs/superpowers/specs/2026-06-13-ai-engineer-resume-and-study-agent-design.md`

## Mission

Upgrade `final-agent` from a **RAG-Powered Study Assistant** into a credible **Adaptive Study Coach Agent**.

The final system should:

1. Accept a learner's review goal.
2. Create a short review plan.
3. Select and invoke typed tools.
4. Retrieve or summarize course material.
5. Generate a quiz question.
6. Pause for the learner's answer.
7. Grade the answer.
8. Persist mastery and tool traces.
9. Adapt the next study step.
10. Publish measured evaluation results.

Do not rename the project to `Adaptive Study Coach Agent` in the resume or README until the evidence gate is satisfied.

## Non-Negotiable Rules

### Accuracy

- Do not invent metrics.
- Do not claim latency, accuracy, grounding rate, or tool-selection accuracy unless measured by a saved evaluation run.
- Do not claim autonomous Agent behavior until the LangGraph workflow can plan, call tools, pause, grade, update memory, and resume.
- Do not claim production quality unless CI, tests, and documentation support the claim.

### Failure and Decision Logging

- Every blocked task, failed command, bug, unexpected behavior, discarded approach, and meaningful design decision must be recorded in `interviewer-note.md`.
- Record the issue immediately when it blocks progress or changes the plan. Do not wait until the end of the phase.
- After resolving it, update the same entry with root cause, fix, verification command, result, and the final decision.
- For design choices, record at least two considered options, their trade-offs, the chosen option, and why it won.
- Do not delete earlier failure notes after fixing them. The point is to preserve the debugging and decision trail for interviews.
- If an AI worker cannot update `interviewer-note.md` because of file conflicts or missing context, it must stop and ask one focused question.

### Scope

- Build one bounded LangGraph agent, not a multi-agent system.
- Maximum six tool calls per run.
- Keep existing RAG modules as the knowledge layer.
- Prefer a complete working loop over broad feature expansion.
- Do not add streaming, dashboards, or visual polish before core Agent behavior passes tests.

### Engineering

- Use TDD for new modules.
- Unit tests must not require API keys, ChromaDB data, model downloads, or network access.
- Use monkeypatching or fakes for LLM, VLM, reranker, vector store, and database boundaries.
- Keep interfaces typed with Pydantic.
- Return structured error results from tools instead of leaking uncaught exceptions.
- Commit after each completed task when working in a Git repository.

## Current Baseline

The current project already includes:

- PDF/Markdown ingestion.
- Doubao VLM PDF parsing.
- Page-aware chunking.
- ChromaDB vector storage.
- BM25 sparse index persistence.
- Dense + sparse retrieval.
- RRF fusion.
- Cross-encoder reranking.
- Citation-grounded answer generation.
- Semantic hallucination checks.
- Course filtering.
- Five study modes.
- Streamlit UI.

Known gaps:

- No automated test suite yet.
- No fixed evaluation dataset yet.
- No Agent planner/tool loop yet.
- No persistent learner memory yet.
- No FastAPI Agent session API yet.
- No measured final metrics yet.

## Required `interviewer-note.md` Logging Format

Append entries under the relevant phase. If no matching phase exists yet, create one using this shape:

```markdown
## Phase N - <short phase name>

### Issue: <short problem title>

- **Date:** YYYY-MM-DD
- **Status:** blocked | investigating | resolved | deferred
- **Where:** `<file/path.py>` or command name
- **Symptom:** What failed or got stuck.
- **Root cause:** What actually caused it. Use `unknown` while investigating, then replace it after resolution.
- **Options considered:**
  - Option A: benefit, drawback.
  - Option B: benefit, drawback.
- **Decision:** Chosen option and reason.
- **Fix:** What changed.
- **Verification:** Exact command or manual check used.
- **Result:** Pass/fail result and any remaining limitation.
- **Resume impact:** none | can mention after measured | must not mention
```

For small command failures, use a compact table row:

```markdown
| Date | Phase | Problem | Cause | Fix | Verification | Decision / Trade-off |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | Phase N | `pytest` failed on graph routing | Fake tool returned unsupported status | Normalized status enum in test fixture | `pytest tests/agent/test_graph.py -v` passed | Kept strict enum validation instead of accepting arbitrary strings |
```

Minimum logging triggers:

- A command fails twice.
- A test is skipped, xfailed, or rewritten.
- A dependency is added, removed, pinned, or replaced.
- A planned file or interface changes.
- A workaround is introduced.
- A metric is worse than expected.
- A feature is deferred.
- A model/API/provider choice changes.
- Any bug would be useful to explain in an interview.

## Target Architecture

```text
Streamlit UI
    |
    v
FastAPI Agent Service
    |
    v
LangGraph Orchestrator
    |-- search_course_material
    |-- summarize_course
    |-- generate_quiz
    |-- grade_answer
    |-- get_learning_profile
    |-- update_mastery
    |
    v
Existing RAG Pipeline
    |
    v
SQLite Learner Memory + Tool Trace Store
```

## Phase Overview

| Phase | Name | Purpose | Exit Evidence |
|---|---|---|---|
| 0 | Orientation | Understand existing code and constraints | AI can explain current data flow and evidence gates |
| 1 | Baseline Tests | Stabilize current RAG behavior | Deterministic tests pass without external services |
| 2 | Evaluation Harness | Create measurable baseline | 30-case baseline suite and JSON report |
| 3 | Tool Contracts | Wrap current capabilities as tools | Typed tool models and adapter tests pass |
| 4 | Agent Graph | Add bounded LangGraph workflow | Plan, tool call, pause, resume, fail-safe tests pass |
| 5 | Memory | Persist learner state and traces | SQLite repository and mastery tests pass |
| 6 | API | Expose Agent sessions | FastAPI contract tests pass |
| 7 | UI | Add Study Coach mode | Manual workflow succeeds end-to-end |
| 8 | Final Evaluation | Produce portfolio evidence | Final metrics, README, demo, and limitations |

## Phase 0: Orientation

### Goal

Build enough context to avoid accidental rewrites or inflated claims.

### Read First

- `README.md`
- `DESIGN.md`
- `interviewer-note.md`
- `src/final_agent/schemas.py`
- `src/final_agent/retrieval/pipeline.py`
- `src/final_agent/generation/answer_generator.py`
- `src/final_agent/generation/summarizer.py`
- `src/final_agent/ui/app.py`
- `docs/superpowers/plans/2026-06-13-adaptive-study-coach-agent.md`

### Required Explanation

Before editing, the AI worker should be able to explain:

```text
PDF or Markdown
  -> chunking
  -> embedding and BM25 indexing
  -> hybrid search
  -> reranking
  -> generation
  -> hallucination guard
  -> UI display
```

### Logging Requirement

Before leaving Phase 0, add a short `interviewer-note.md` entry summarizing:

- Current architecture understanding.
- Known gaps.
- The chosen one-agent approach.
- Why multi-agent orchestration is deferred.

### Stop Conditions

Stop and ask one focused question if:

- The target project root is unclear.
- API keys are required for a test that should be offline.
- Existing files differ materially from the plan.

## Phase 1: Baseline Tests

### Goal

Lock down existing behavior before adding Agent features.

### Build

- `tests/conftest.py`
- `tests/test_schemas.py`
- `tests/retrieval/test_hybrid_searcher.py`
- `tests/retrieval/test_pipeline.py`
- `tests/ingestion/test_chunker.py`

### Metrics

| Metric | Target |
|---|---|
| Schema round-trip tests | Pass |
| RRF ranking tests | Pass |
| Course filtering tests | Pass |
| Page-aware chunking tests | Pass |
| External API usage in tests | 0 |

### Evidence

Run:

```bash
pytest tests/test_schemas.py tests/retrieval tests/ingestion -v
```

Record:

- Test count.
- Failure count.
- Any intentionally skipped tests.

### Logging Requirement

Append every baseline failure to `interviewer-note.md`. If a test reveals existing behavior that is buggy but intentionally preserved, record that as a decision with trade-offs.

## Phase 2: Evaluation Harness

### Goal

Create a repeatable baseline so later Agent improvements can be measured.

### Build

- `src/final_agent/evaluation/models.py`
- `src/final_agent/evaluation/dataset.py`
- `src/final_agent/evaluation/metrics.py`
- `src/final_agent/evaluation/runner.py`
- `tests/evaluation/test_metrics.py`

### Evaluation Dataset

Create 30 fixed cases:

- 10 retrieval and citation-grounding cases.
- 10 tool-selection and workflow cases.
- 10 adaptive-review and memory cases.

Each case must include:

- `case_id`
- `category`
- `course_ids`
- `user_input`
- `expected_tools`
- `required_citations`
- `expected_outcome`

### Metrics

| Metric | Definition |
|---|---|
| Task completion rate | Completed cases / total cases |
| Tool-selection accuracy | Exact expected tool sequence match or accepted partial-credit rule |
| Citation-grounding rate | Required citations present and valid / required citations |
| Grading agreement | Grader output matches expected scoring band |
| Mean latency | Average elapsed wall-clock time per case |
| P95 latency | 95th percentile elapsed wall-clock time |
| Error rate | Failed cases / total cases |

### Evidence

Run:

```bash
python -m final_agent.evaluation.runner --suite baseline
```

Output:

- `data/evaluation/baseline.json`

Do not optimize before this baseline exists.

### Logging Requirement

Record dataset-design decisions in `interviewer-note.md`, including why each metric is included and what it cannot prove. If a metric is hard to calculate reliably, document the chosen approximation and its weakness.

## Phase 3: Tool Contracts

### Goal

Expose existing capabilities as explicit, testable tools.

### Required Tools

| Tool | Purpose |
|---|---|
| `search_course_material` | Retrieve relevant chunks for a user query |
| `summarize_course` | Produce page/full/key-point summaries |
| `generate_quiz` | Generate a quiz question from retrieved material |
| `grade_answer` | Grade the learner answer against expected points |
| `get_learning_profile` | Fetch mastery and past attempts |
| `update_mastery` | Persist new mastery state |

### Contract Rules

Each tool must:

- Have a Pydantic input model.
- Have a Pydantic output model or a `ToolResult`.
- Return `ok=False` on recoverable errors.
- Record elapsed time.
- Avoid logging secrets or full prompts.
- Be testable without network calls.

### Metrics

| Metric | Target |
|---|---|
| Tool adapter unit tests | Pass |
| Tool calls requiring real APIs in tests | 0 |
| Unsupported-tool behavior | Explicit failure |
| Error result shape | Stable and documented |

### Logging Requirement

For each tool, record any adapter mismatch between the planned contract and the existing RAG function signatures. If the adapter hides complexity or changes return shape, document the trade-off.

## Phase 4: Agent Graph

### Goal

Implement a bounded LangGraph workflow.

### Required Nodes

```text
understand_goal
create_plan
select_tool
execute_tool
request_answer
grade_answer
update_mastery
choose_next_step
finish
```

### Routing Rules

- Route from state fields, not free-form prose.
- Validate tool names against the registry.
- Stop at six tool calls.
- Mark unsupported tools as failed.
- Interrupt before grading if the learner answer is missing.
- Resume the same session after the answer arrives.

### Agent State Minimum

```python
AgentState:
    session_id: str
    learning_goal: str
    course_ids: list[str]
    plan: list[StudyPlanStep]
    current_step: int
    quiz: QuizQuestion | None
    learner_answer: str
    grade: GradeResult | None
    tool_trace: list[ToolTraceEntry]
    tool_call_count: int
    status: "planning" | "running" | "waiting_for_answer" | "completed" | "failed"
```

### Metrics

| Metric | Target |
|---|---|
| Graph happy-path test | Pass |
| Unsupported-tool test | Pass |
| Six-call-limit test | Pass |
| Pause/resume test | Pass |
| Tool failure test | Pass |
| Infinite-loop risk | 0 known paths |

### Logging Requirement

Record all graph-routing decisions in `interviewer-note.md`, especially:

- Why routing is state-driven rather than prose-driven.
- Why the tool-call limit is six.
- How unsupported tools fail.
- How pause/resume is implemented.

## Phase 5: Memory and Adaptation

### Goal

Persist learner mastery and use it to choose the next study action.

### SQLite Tables

```text
sessions(id PK, learning_goal, status, state_json, created_at, updated_at)
mastery(session_id FK, topic, score, attempts, updated_at, UNIQUE(session_id, topic))
quiz_attempts(id PK, session_id FK, question_id, topic, answer, score, feedback, created_at)
tool_traces(id PK, session_id FK, sequence_no, tool_name, input_summary, ok, elapsed_ms, error, created_at)
```

### Mastery Rule

```python
new_score = clamp(0.7 * previous_score + 0.3 * latest_score, 0.0, 1.0)
```

Action selection:

| Score | Action |
|---|---|
| `< 0.4` | Re-explain and ask easier question |
| `0.4 - 0.7` | Ask same-level variant |
| `> 0.7` | Advance topic |

### Metrics

| Metric | Target |
|---|---|
| Repository tests | Pass |
| Session isolation | Pass |
| Mastery update tests | Pass |
| Trace ordering tests | Pass |
| Transaction rollback tests | Pass |

### Logging Requirement

Record memory-schema and mastery-formula decisions in `interviewer-note.md`. Include why SQLite is sufficient for version 1 and what would trigger a future migration.

## Phase 6: FastAPI Agent API

### Goal

Expose the Agent workflow as session-based APIs.

### Endpoints

```text
POST /sessions
POST /sessions/{id}/messages
GET  /sessions/{id}
GET  /sessions/{id}/mastery
GET  /sessions/{id}/trace
```

### Response Rules

- Return `404` for unknown sessions.
- Return `409` when the message conflicts with current session state.
- Return `422` for invalid payloads.
- Return `503` for temporary model/retrieval failures.
- Never expose raw database rows or internal graph dictionaries.

### Metrics

| Metric | Target |
|---|---|
| FastAPI contract tests | Pass |
| Unknown session behavior | 404 |
| Invalid payload behavior | 422 |
| Conflict behavior | 409 |
| Temporary dependency failure | 503 |

### Logging Requirement

Record API status-code decisions in `interviewer-note.md`, especially 409 versus 400, 503 versus 500, and what client behavior each status is meant to trigger.

## Phase 7: Study Coach UI

### Goal

Add a UI mode that makes the Agent behavior visible and testable.

### UI Requirements

Display:

- Learning goal.
- Generated plan.
- Current question.
- Learner answer input.
- Grading feedback.
- Mastery score.
- Suggested next action.
- Expandable tool trace.

Preserve existing RAG modes.

### Metrics

| Metric | Target |
|---|---|
| API client tests | Pass |
| Manual end-to-end workflow | Pass |
| Existing RAG modes | Still usable |
| Tool trace visibility | Present |
| Mastery visibility | Present |

### Logging Requirement

Record UX trade-offs in `interviewer-note.md`: what the UI exposes, what it hides, and how tool trace visibility helps debugging and interviews.

## Phase 8: Final Evaluation and Portfolio Evidence

### Goal

Measure the final Agent and prepare evidence for resume and interviews.

### Required Commands

```bash
ruff check src tests
pytest --cov=final_agent --cov-report=term-missing
python -m final_agent.evaluation.runner --suite agent-final
```

### Required Outputs

- `data/evaluation/agent-final.json`
- Updated `README.md`
- Updated `DESIGN.md`
- Updated `interviewer-note.md`
- Architecture diagram.
- Example tool trace.
- 90-second demo script or video notes.

### Final Metrics to Report

Only report measured values:

| Metric | Source |
|---|---|
| Test count | pytest output |
| Test pass rate | pytest output |
| Coverage | coverage output |
| Task completion rate | `agent-final.json` |
| Tool-selection accuracy | `agent-final.json` |
| Citation-grounding rate | `agent-final.json` |
| Grading agreement | `agent-final.json` |
| Mean latency | `agent-final.json` |
| P95 latency | `agent-final.json` |
| Error rate | `agent-final.json` |

### Logging Requirement

Before changing README or resume bullets, add a final evaluation note to `interviewer-note.md` with:

- Exact commands run.
- Metric results.
- Failed cases.
- Known limitations.
- Which claims are now allowed on the resume.
- Which claims remain forbidden.

## Resume Upgrade Gate

Keep the resume project title as:

```text
RAG-Powered Study Assistant
```

Upgrade it to:

```text
Adaptive Study Coach Agent
```

only after all are true:

- LangGraph workflow works end-to-end.
- Tools are typed and tested.
- Learner memory persists.
- FastAPI session API exists.
- Study Coach UI works.
- Final 30-case evaluation report exists.
- README documents measured results.

Allowed resume bullets after the gate:

```text
Built a LangGraph-based study agent that plans review workflows and invokes retrieval, summarization, quiz-generation, and grading tools.

Implemented persistent learner memory to track mastery, identify weak topics, and adapt subsequent review tasks.

Exposed session workflows through FastAPI and evaluated tool selection, citation grounding, grading agreement, and task completion across 30 fixed scenarios.
```

Add numeric metrics only after replacing placeholders with measured values from `agent-final.json`.

## AI Self-Check Questions

Before each phase, answer these internally:

1. What existing behavior might this phase break?
2. Which tests prove it did not break?
3. Which metric will this phase improve or make measurable?
4. Is any claim in README or resume ahead of implemented evidence?
5. Can this phase be completed without adding unrelated scope?
6. Have all blocked, failed, deferred, or trade-off-heavy decisions been recorded in `interviewer-note.md`?

If any answer is unclear, stop and ask one focused question.

## Done Criteria

The improvement is done when:

- `ruff check src tests` exits 0.
- `pytest --cov=final_agent --cov-report=term-missing` exits 0.
- `python -m final_agent.evaluation.runner --suite agent-final` produces a complete report.
- The Study Coach can complete this loop:

```text
goal -> plan -> retrieve/summarize -> quiz -> learner answer -> grade -> mastery update -> next action
```

- The repository documents architecture, setup, known limitations, final metrics, and a demo path.
