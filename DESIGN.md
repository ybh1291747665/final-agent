# final-agent Design

## Purpose

`final-agent` started as a RAG-powered study assistant. The current improvement adds a bounded adaptive study coach around the existing knowledge layer without replacing the ingestion, retrieval, generation, or Streamlit workflows.

The first release intentionally favors a complete, testable learning loop over broad autonomy.

## Current Status

Implemented and verified in the current branch:

- Bounded LangGraph study workflow with typed tool contracts.
- SQLite learner memory and ordered tool-trace persistence.
- FastAPI session API for study coach runs.
- Streamlit Study Coach mode layered on top of the existing RAG UI.
- Deterministic evaluation harness with baseline and `agent-final` reports.
- Local-course `agent-final` evaluation that reads `data/markdown`, reuses the page-aware chunker, and runs the workflow through a deterministic local search adapter.

Latest measured evidence:

- `pytest tests/test_schemas.py tests/retrieval tests/ingestion tests/evaluation tests/agent tests/memory tests/api tests/ui -q`: 31 passed.
- `python -m ruff check src tests`: passed.
- `pytest --cov=final_agent --cov-report=term-missing`: 31 passed, 44% total coverage.
- `data/evaluation/agent-final.json`: 30 cases, 100% task completion, 100% tool-selection accuracy, 66.7% citation grounding, 100% grading agreement, 0% error rate.
- `docs/final-agent-study-coach-demo-evidence.md`: manual `FastAPI -> workflow -> SQLite` Study Coach walkthrough with example mastery and ordered tool trace.

What this evidence means:

- The bounded study-coach loop is implemented and testable offline.
- The final evaluation uses real local Markdown chunks when available.
- The manual evidence package proves the API/UI workflow can pause, resume, persist mastery, and surface tool traces in a reproducible local environment.
- The evaluation and manual demo do not yet prove live LLM quality, production retrieval quality, or end-user polish.

## Existing Knowledge Layer

```text
PDF or Markdown
    -> Doubao PDF parsing or Markdown import
    -> page-aware chunking
    -> embeddings + ChromaDB
    -> BM25 sparse index
    -> hybrid search
    -> RRF fusion
    -> reranking
    -> answer generation
    -> hallucination guard
    -> UI display
```

The knowledge layer remains the source of truth for course material retrieval and summarization.

## Study Coach Layer

```text
FastAPI Agent Service
    -> deterministic planner
    -> typed tool registry
    -> bounded workflow
    -> SQLite learner memory
    -> trace persistence
```

The v1 workflow creates a short plan, generates a quiz question, waits for the learner answer, grades expected-point coverage, updates mastery, and chooses the next action.

## Public Contracts

Agent status values:

```text
planning | running | waiting_for_answer | completed | failed
```

Required tools:

```text
search_course_material
summarize_course
generate_quiz
grade_answer
get_learning_profile
update_mastery
```

Agent state includes:

- session ID
- learning goal
- course IDs
- study plan
- current quiz
- learner answer
- grade
- tool trace
- tool-call count
- terminal status

The tool-call limit is six per run. Unsupported tools fail explicitly.

## Memory

SQLite is sufficient for v1 because the app is local-first and session volume is small. SQLAlchemy Core is used for explicit schema and transaction boundaries without adding a full ORM model layer.

Tables:

```text
sessions(id PK, learning_goal, status, state_json, created_at, updated_at)
mastery(session_id FK, topic, score, attempts, updated_at, UNIQUE(session_id, topic))
quiz_attempts(id PK, session_id FK, question_id, topic, answer, score, feedback, created_at)
tool_traces(id PK, session_id FK, sequence_no, tool_name, input_summary, ok, elapsed_ms, error, created_at)
```

Mastery update:

```python
new_score = clamp(0.7 * previous_score + 0.3 * latest_score, 0.0, 1.0)
```

Action selection:

| Score | Action |
|---|---|
| `< 0.4` | re-explain and ask an easier question |
| `0.4 - 0.7` | ask a same-level variant |
| `> 0.7` | advance topic |

## API

```text
POST /sessions
POST /sessions/{id}/messages
GET  /sessions/{id}
GET  /sessions/{id}/mastery
GET  /sessions/{id}/trace
```

Status-code policy:

- `404` for unknown sessions.
- `409` for messages that conflict with the current session state.
- `422` for invalid payloads.
- `503` for temporary model or retrieval dependency failures.

Responses expose typed session state and never raw database rows or graph internals.

## Evaluation

The current harness uses 30 deterministic cases. The `baseline` suite uses fixed fixtures. The `agent-final` suite reads local Markdown under `data/markdown` when available, chunks it with the same page-aware chunker used by ingestion, derives expected citations from those real course chunks, and runs the agent workflow through a deterministic local search adapter. If local Markdown is unavailable, `agent-final` falls back to the fixed fixtures.

- 10 retrieval and citation-grounding cases.
- 10 tool-selection and workflow cases.
- 10 adaptive-review and memory cases.

Latest local-course report: `data/evaluation/agent-final.json`.

Measured local Markdown results:

| Metric | Value |
|---|---:|
| Total cases | 30 |
| Task completion rate | 100% |
| Tool-selection accuracy | 100% |
| Citation-grounding rate | 66.7% |
| Grading agreement | 100% |
| Error rate | 0% |

These values prove the deterministic harness, local course ingestion path, and agent tool contracts, not live model accuracy. Citation grounding is currently lexical against local Markdown chunks through the evaluation adapter, so it is useful as a repeatable regression signal but not as a production retrieval or generation benchmark.

## Next Work

Recommended next steps after the current evidence package:

1. Replace deterministic quiz generation with a live adapter while keeping the current offline baseline.
2. Replace deterministic grading with a live adapter while keeping regression coverage.
3. Persist retrieved context in agent state so future live quiz/grading stays grounded in course material.
4. Keep the project title as `RAG-Powered Study Assistant` until live model-backed evidence is produced.

## Deferred Scope

- Multi-agent orchestration.
- Streaming.
- Dashboard polish.
- LLM-based grading.
- Resume/title upgrade to "Adaptive Study Coach Agent" before live evidence is produced.
