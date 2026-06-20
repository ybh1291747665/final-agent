# Quiz Generator Adapter Design

## Objective

Replace the hard-coded quiz-generation implementation with an adapter-based design while preserving the existing `QuizQuestion` contract, API shape, UI behavior, and deterministic fallback path.

This phase is intentionally narrow. It upgrades only quiz generation. It does not yet change answer grading or retrieval grounding.

## Current Situation

The current Study Coach workflow calls `generate_quiz()` directly from `agent/tools.py`.

Today that function:

- derives expected points from the learner goal with regex token extraction
- returns a `QuizQuestion`
- is deterministic
- has no injectable implementation boundary

This makes the workflow stable, but it prevents clean introduction of a live LLM-backed quiz path.

## Goal Of This Phase

Introduce a small adapter layer so the workflow can use either:

- a deterministic quiz generator
- an LLM-backed quiz generator

without changing:

- `QuizQuestion`
- the Study Coach API response format
- the Streamlit UI contract
- the grader implementation

## Scope

### In Scope

- Add a dedicated quiz-generator adapter module.
- Keep the current deterministic generator as a first-class implementation.
- Add an `LlmQuizGenerator` that reuses the existing OpenAI-compatible LLM client.
- Require strict JSON output that validates into `QuizQuestion`.
- Fallback to deterministic generation if the LLM call or JSON parsing fails.
- Make generator selection explicit through dependency injection from app/service into the workflow.
- Leave a lightweight observable signal showing whether quiz generation used the LLM path or the fallback path.
- Add focused tests for deterministic generation, LLM success, LLM fallback, and graph injection.

### Out Of Scope

- Replacing the deterministic grader.
- Passing retrieved chunks into quiz generation.
- Changing `AgentState` to persist retrieved context.
- Making LLM-backed quiz generation the default production behavior.
- Changing UI copy, API payloads, or README product claims.
- Adding a new settings surface for quiz-specific provider selection.

## Design Decisions

### 1. Preserve the existing `QuizQuestion` contract

The adapter layer must still return a normal `QuizQuestion` with:

- `question_id`
- `topic`
- `prompt`
- `expected_points`
- `difficulty`

Reason:

- The current grader already depends on `expected_points`.
- This phase should not expand into grading or workflow redesign.

### 2. Split implementations into a dedicated module

Create a new module:

- `src/final_agent/agent/quiz_generators.py`

It should contain:

- a protocol or abstract callable contract for quiz generation
- `DeterministicQuizGenerator`
- `LlmQuizGenerator`
- a small factory function for default assembly

Reason:

- This keeps `tools.py` from turning into branching glue.
- The same pattern can later be applied to grading.

### 3. Reuse the existing LLM client

`LlmQuizGenerator` should reuse:

- `final_agent.generation.llm_client.generate`
- `settings.models_llm`

Reason:

- The codebase already has a stable LLM access path.
- A separate provider/config surface would enlarge scope without helping this first adapter slice.

### 4. Enforce strict JSON and validate with Pydantic

The LLM prompt should require JSON only.

The adapter should:

1. call the LLM
2. parse JSON
3. validate with `QuizQuestion`

If any step fails, it should fallback to `DeterministicQuizGenerator`.

Reason:

- The contract must stay reliable.
- Free-form text parsing would make the workflow fragile and hard to test.

### 5. Fallback should preserve workflow success

LLM failure or malformed output should not make the `generate_quiz` tool fail in this phase.

Instead:

- fallback to deterministic generation
- return `ok=True`
- record a lightweight signal that fallback occurred

Reason:

- This phase is about introducing capability without reducing stability.
- We want observability without lowering session success rate.

### 6. Keep observability lightweight

Do not change the trace schema yet.

Use existing fields to expose implementation choice:

- encode `impl=llm` or `impl=deterministic-fallback` in `input_summary`
- optionally include a short fallback reason in `error`

Reason:

- `ToolTraceEntry` is already persisted to SQLite.
- A schema change would broaden scope unnecessarily.

### 7. Inject the generator from app/service into the workflow

The composition path should be:

- `create_app()` / `AgentService` assembles the quiz generator
- `run_study_turn(...)` accepts it explicitly
- `generate_quiz(...)` in `tools.py` delegates to the injected generator

Reason:

- This keeps startup-time assembly explicit.
- It makes tests simple and avoids hidden global state.

### 8. Keep the first live path goal-based

The first `LlmQuizGenerator` should only use:

- `learning_goal`
- optional `course_ids`

It should not yet use retrieved chunks.

Reason:

- Retrieval grounding belongs to the later state/data-flow phase.
- This keeps the present change focused on adapterization only.

## Files Expected To Change

### New

- `src/final_agent/agent/quiz_generators.py`
- `tests/agent/test_quiz_generators.py`

### Existing

- `src/final_agent/agent/tools.py`
- `src/final_agent/agent/graph.py`
- `src/final_agent/api/app.py`
- `tests/agent/test_graph.py`
- `tests/agent/test_tools.py`
- `interviewer-note.md`

## Testing Strategy

Focus only on the new seam:

1. deterministic adapter returns stable `QuizQuestion`
2. LLM adapter returns validated `QuizQuestion` on well-formed JSON
3. LLM adapter falls back to deterministic output on bad JSON or call failure
4. graph accepts injected generator and stores the produced quiz in state

Do not expand test scope to grading or grounding in this phase.

## Follow-Up Phase

After this adapter slice is stable, the next steps should be:

1. add a parallel adapter layer for grading
2. make startup-time generator selection configurable
3. persist retrieval results in state so quiz/grading can become grounded in retrieved course material
