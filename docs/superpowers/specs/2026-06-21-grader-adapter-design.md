# Grader Adapter Design

## Objective

Introduce an injectable grader adapter layer for Study Coach while preserving the existing `GradeResult` contract, API shape, UI behavior, and current workflow success guarantees.

This phase is intentionally narrow. It upgrades only grading. It does not yet persist retrieved materials into `AgentState`, and it does not yet make quiz generation configurable.

## Current Situation

The current Study Coach workflow grades learner answers by calling `grade_answer()` directly from `agent/tools.py`.

Today that function:

- compares `expected_points` against the learner answer with deterministic string matching
- returns a `GradeResult`
- has no injectable implementation boundary
- has no LLM path or fallback metadata

This keeps grading stable, but it prevents clean introduction of an LLM-backed grader and leaves grading less configurable than quiz generation.

## Goal Of This Phase

Introduce a small adapter layer so the workflow can use either:

- a deterministic grader
- an LLM-backed grader with deterministic fallback

without changing:

- `GradeResult`
- the Study Coach API response format
- the Streamlit UI contract
- the current retrieval flow

## Scope

### In Scope

- Add a dedicated grader adapter module.
- Keep the current deterministic scoring logic as a first-class implementation.
- Add an `LlmGrader` that reuses the existing OpenAI-compatible LLM client.
- Require strict JSON output that validates into `GradeResult`.
- Fallback to deterministic grading if the LLM call, JSON parsing, or validation fails.
- Make grader selection explicit through dependency injection from app/service into the workflow.
- Add lightweight observability showing whether grading used the LLM path or the fallback path.
- Add a `materials` input parameter to the grader interface, but leave it empty in this phase.
- Make app startup assemble `LlmGrader(fallback=DeterministicGrader())` as the default grader.
- Add focused tests for deterministic grading, LLM success, LLM fallback, graph injection, and API assembly.

### Out Of Scope

- Persisting retrieved chunks or citations into `AgentState`.
- Re-querying retrieval during grading.
- Changing the `GradeResult` schema.
- Changing quiz-generator defaults.
- Adding a new settings/config surface for grading implementation selection.
- Changing UI copy, API payloads, or README product claims.

## Design Decisions

### 1. Preserve the existing `GradeResult` contract

The adapter layer must still return a normal `GradeResult` with:

- `score`
- `covered_points`
- `missed_points`
- `feedback`

Reason:

- The current workflow, persistence path, and UI already consume this shape.
- This phase should not expand into a grading-schema redesign.

### 2. Split implementations into a dedicated module

Create a new module:

- `src/final_agent/agent/graders.py`

It should contain:

- a grader-facing interface shape
- `DeterministicGrader`
- `LlmGrader`
- `GradeEvaluationMeta`

Reason:

- This keeps `tools.py` from becoming branching glue.
- It mirrors the adapter boundary already introduced for quiz generation.

### 3. Reuse the existing LLM client

`LlmGrader` should reuse:

- `final_agent.generation.llm_client.generate`
- `settings.models_llm`

Reason:

- The codebase already has a stable LLM access path.
- A second provider/config system would enlarge scope unnecessarily.

### 4. Enforce strict JSON and validate with Pydantic

The LLM prompt should require JSON only.

The adapter should:

1. call the LLM
2. parse JSON
3. validate with `GradeResult`

If any step fails, it should fallback to `DeterministicGrader`.

Reason:

- The grading contract must stay reliable.
- Free-form parsing would be fragile and hard to test.

### 5. Fallback should preserve workflow success

LLM failure or malformed output should not make the grading tool fail in this phase.

Instead:

- fallback to deterministic grading
- return `ok=True`
- record a lightweight signal that fallback occurred

Reason:

- This phase introduces new capability without lowering session completion reliability.
- We want observability without making grading brittle.

### 6. Keep observability lightweight

Do not change the trace schema yet.

Use existing fields to expose implementation choice:

- encode `impl=llm` or `impl=deterministic-fallback` in `input_summary`
- include a short fallback reason in `error` when fallback occurs

Reason:

- `ToolTraceEntry` is already persisted to SQLite.
- A schema change would broaden scope unnecessarily.

### 7. Inject the grader from app/service into the workflow

The composition path should be:

- `create_app()` / `AgentService` assembles the grader
- `run_study_turn(...)` accepts it explicitly
- `grade_answer(...)` in `tools.py` delegates to the injected grader

Reason:

- This keeps startup-time assembly explicit.
- It matches the quiz adapter pattern and keeps testing simple.

### 8. Reserve a `materials` input without using grounded grading yet

The grader interface should accept:

- `question`
- `expected_points`
- `learner_answer`
- `materials`

In this phase, `materials` should be passed as an empty list.

Reason:

- This creates the interface seam needed for future grounded grading.
- It avoids expanding this phase into `AgentState` or retrieval-flow changes.

### 9. Default startup behavior should favor the LLM path with safe fallback

At app startup, the default grader should be:

- `LlmGrader(fallback=DeterministicGrader())`

Reason:

- The user wants the deployed system to begin using the new grading capability immediately.
- Deterministic fallback keeps the workflow resilient when the LLM path is unavailable or malformed.

## Files Expected To Change

### New

- `src/final_agent/agent/graders.py`
- `tests/agent/test_graders.py`

### Existing

- `src/final_agent/agent/tools.py`
- `src/final_agent/agent/graph.py`
- `src/final_agent/api/app.py`
- `tests/agent/test_tools.py`
- `tests/agent/test_graph.py`
- `tests/api/test_sessions.py`
- `interviewer-note.md`

## Testing Strategy

Focus only on the new seam:

1. deterministic grader returns the same scoring behavior as today
2. LLM grader returns validated `GradeResult` on well-formed JSON
3. LLM grader falls back to deterministic grading on bad JSON, call failure, or validation failure
4. `grade_answer(...)` delegates to the injected grader
5. graph accepts an injected grader and records `impl=...` on the `grade_answer` trace
6. `AgentService` passes the assembled grader into the workflow

Do not expand test scope to retrieval grounding or state persistence in this phase.

## Deployment Implication

After this phase:

- quiz generation still defaults to deterministic assembly
- grading defaults to `LlmGrader(fallback=DeterministicGrader())`

So a deployed environment with working `models_llm` settings will begin using LLM-backed grading automatically, while still completing sessions when the LLM path fails.

If later we want deployment-time control without code changes, the next phase should add a thin settings surface such as:

- `settings.study_coach.quiz_generator = deterministic | llm`
- `settings.study_coach.grader = deterministic | llm`

That configuration work is intentionally deferred.

## Follow-Up Phase

After this adapter slice is stable, the next steps should be:

1. make quiz and grader implementation selection configurable at startup
2. persist retrieval results in `AgentState`
3. pass grounded materials into quiz generation and grading
