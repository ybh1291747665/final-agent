# Final Evidence Package Design

## Objective

Close the remaining evidence gap for `final-agent` without expanding scope into new study-agent capabilities.

This phase is about making the implemented bounded study-coach workflow reviewable, demonstrable, and honestly documented.

## Current Situation

The repository already has:

- A bounded study-coach workflow.
- Typed tools and tool traces.
- SQLite learner memory.
- FastAPI session APIs.
- Streamlit Study Coach mode.
- Offline evaluation reports with saved JSON output.

The remaining gap is not core implementation. The gap is portfolio-quality evidence:

- The Study Coach UI does not yet visibly expose all promised fields.
- One FastAPI/Starlette test warning remains.
- There is no dedicated demo/evidence document.
- README does not yet link to a concrete walkthrough with a clean example trace.

## Goal of This Phase

Publish a small, honest, review-ready evidence package that proves:

1. The Study Coach UI can drive a full happy-path session.
2. The FastAPI session API persists state and traces correctly.
3. SQLite mastery updates are visible after a learner answer.
4. The repository documents exactly what is measured versus what remains deterministic or deferred.

## Scope

### In Scope

- Fill the Study Coach UI visibility gap by showing:
  - mastery
  - next action
  - expandable tool trace
- Remove the remaining FastAPI/Starlette third-party warning from tests.
- Run and document one manual happy-path demo using local course material under `data/markdown`.
- Publish evidence in two layers:
  - README summary + link
  - dedicated evidence document in `docs/`
- Update `interviewer-note.md` as decisions and fixes happen.

### Out of Scope

- Replacing deterministic quiz generation with live LLM generation.
- Replacing deterministic grading with LLM grading.
- Reworking agent state to persist retrieved chunks for grounded live grading.
- Renaming the project to `Adaptive Study Coach Agent`.
- Adding streaming, dashboards, or unrelated UI polish.

## Design Decisions

### 1. Keep the title conservative

Keep the public title as `RAG-Powered Study Assistant` during this phase.

Reason:

- The current manual demo can prove real `Streamlit -> FastAPI -> workflow -> SQLite` integration.
- It does not prove live LLM-backed quiz generation or grading.

### 2. Treat the demo as integration evidence, not live-model evidence

The evidence package must explicitly state:

- `search_course_material` connects to the existing knowledge layer.
- `generate_quiz` and `grade_answer` remain deterministic v1 logic.
- The demo proves workflow integration and persistence, not production LLM quality.

### 3. Use local course material for reproducibility

The manual walkthrough should use existing local Markdown course files under `data/markdown`.

Recommended learner goal:

- `review configuration management and version control`

Reason:

- It aligns naturally with the available local course content.
- It produces a more readable deterministic quiz than placeholder inputs such as `review CI`.

### 4. Show a partial-credit path

The demo answer should be intentionally partially correct so the resulting mastery lands in the mid band and triggers `practice_variant`.

Reason:

- This demonstrates adaptive behavior better than an immediate perfect score.

### 5. Publish evidence in two layers

README should stay high-signal and lightweight.

The detailed walkthrough should live in:

- `docs/final-agent-study-coach-demo-evidence.md`

That document should contain:

- setup assumptions
- happy-path walkthrough
- sample session response excerpts
- sample mastery result
- sample tool trace
- 90-second demo script
- known limitations of this demo

## Execution Order

Work in this sequence:

1. Update the Study Coach UI to expose promised state.
2. Fix the remaining API test warning.
3. Run and record one manual happy-path demo.
4. Update README, DESIGN, `interviewer-note.md`, and add the dedicated evidence doc.

This order reduces document drift and keeps the evidence package aligned with the real product state.

## UI Design Changes

The existing Study Coach panel already shows:

- status
- plan
- current question
- grade

This phase should add:

- visible mastery summary after each answer
- visible next action after grading
- expandable ordered tool trace

The UI should favor clarity over polish. It is evidence-facing, not redesign-facing.

## Testing and Verification

Minimum verification for this phase:

- targeted UI/API tests for the new display behavior
- targeted warning-removal verification for API tests
- full project verification before claiming completion:
  - `python -m ruff check src tests`
  - `pytest --cov=final_agent --cov-report=term-missing`
  - `python -m final_agent.evaluation.runner --suite agent-final --data-dir data`

The manual demo must be documented with the exact learner goal, answer, and observed outputs.

## Known Limits to Preserve in Documentation

Documentation must continue to say:

- quiz generation is deterministic in v1
- grading is expected-point based in v1
- local evaluation is not a live-model benchmark
- the evidence package proves bounded workflow behavior and integration quality, not production autonomy

## Follow-Up Phase After Deployment

Do not implement these changes in this phase, but keep them as the next architecture step:

- add adapter/strategy layers for quiz generation and grading
- assemble deterministic or live adapters at app startup
- keep deterministic adapters for tests and offline evaluation
- persist retrieval results in agent state so future live quiz/grading can be grounded in retrieved course chunks
