# final-agent Design

## Purpose

`final-agent` started as a RAG-powered study assistant. The current improvement adds a bounded adaptive study coach around the existing knowledge layer without replacing the ingestion, retrieval, generation, or Streamlit workflows.

The first release intentionally favors a complete, testable learning loop over broad autonomy.

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

The current harness uses 30 fixed fixture cases:

- 10 retrieval and citation-grounding cases.
- 10 tool-selection and workflow cases.
- 10 adaptive-review and memory cases.

Latest fixture report: `data/evaluation/agent-final.json`.

Measured fixture results:

| Metric | Value |
|---|---:|
| Total cases | 30 |
| Task completion rate | 100% |
| Tool-selection accuracy | 33.3% |
| Citation-grounding rate | 100% |
| Grading agreement | 50% |
| Error rate | 0% |

These values prove the deterministic harness and contracts, not live model accuracy. Citation grounding is fixture-derived in this harness.

## Deferred Scope

- Multi-agent orchestration.
- Streaming.
- Dashboard polish.
- LLM-based grading.
- Resume/title upgrade to "Adaptive Study Coach Agent" before live evidence is produced.
