# Multi-Agent Study Coach Design

## Goal

Upgrade the current bounded Study Coach workflow into a bounded multi-agent learning workflow with fixed roles, internal typed tool calling, role-level tool boundaries, explainable agent traces, and non-blocking critic warnings.

This is not a generic autonomous agent platform. It remains a local-first study assistant built around course material, retrieval-grounded learning, deterministic fallback behavior, and testable session workflows.

## Current Context

The current system already has:

- A course-scoped knowledge base with Chroma collections, BM25 snapshots, metadata, and incremental build skipping.
- A hybrid retrieval and generation layer used by Streamlit RAG modes.
- A bounded Study Coach workflow in `src/final_agent/agent/graph.py`.
- Typed tools in `src/final_agent/agent/tools.py`.
- Quiz and grader adapters with deterministic fallback.
- SQLite session, mastery, quiz attempt, and tool trace persistence.
- FastAPI `/sessions` endpoints consumed by Streamlit through `AgentApiClient`.

The multi-agent upgrade should evolve this workflow, not fork it into a second product path.

## Canonical Terms

The glossary in `CONTEXT.md` defines the terms used by this design:

- `Multi-Agent Study Coach`
- `Bounded Agent Workflow`
- `Fixed Sequential Collaboration`
- `Agent State`
- `Supervisor Agent`
- `Retrieval Agent`
- `Quiz Agent`
- `Grader Agent`
- `Coach Agent`
- `Critic Agent`
- `Critic Warning`
- `Tool Boundary`
- `Internal Typed Tool Calling`
- `Agent Tool Trace`
- `Study Coach Session API`
- `Multi-Agent Execution Skeleton`

## Stage 1 Scope

Stage 1 builds the execution skeleton:

- `AgentRole`
- `ToolCall`
- `ToolSpec`
- `ToolRegistry`
- Role-level allowed tools
- Fixed sequential orchestrator
- `AgentToolTrace`
- `CriticWarning`
- Backward-compatible API response extensions
- Streamlit agent timeline visibility
- Deterministic tests

Stage 1 does not build:

- LLM supervisor autonomous planning
- Provider-native function calling as the core contract
- Parallel agent execution
- Retry/regenerate control loops
- A new `/multi-agent/*` API namespace

## Role Model

Stage 1 has exactly six fixed roles.

### Supervisor Agent

Owns the study turn plan and coordinates the fixed role sequence. It does not directly call business tools.

Allowed tools: none.

### Retrieval Agent

Finds course-grounded material and prepares evidence for downstream agents.

Allowed tools:

- `search_course_material`
- `summarize_course`

### Quiz Agent

Creates a learner-facing quiz from the current goal and retrieved course evidence.

Allowed tools:

- `generate_quiz`

### Grader Agent

Evaluates the learner answer against expected points and available course evidence.

Allowed tools:

- `grade_answer`

### Coach Agent

Updates learner mastery and chooses the next study action.

Allowed tools:

- `get_learning_profile`
- `update_mastery`

### Critic Agent

Checks whether evidence, grading, and next action are internally consistent before the response is returned.

Allowed tools:

- `verify_evidence`
- `verify_grade_consistency`

Critic warnings are non-blocking in Stage 1.

## Fixed Sequential Collaboration

The first version uses a fixed sequence:

```text
Supervisor
  -> Retrieval
  -> Quiz
  -> wait_for_answer
  -> Grader
  -> Coach
  -> Critic
  -> final response
```

This preserves the current Study Coach learning loop while making role boundaries and tool calls explicit.

Parallel role execution and dynamic routing are Stage 2 candidates.

## Internal Typed Tool Calling

Stage 1 uses a project-owned tool calling protocol.

```text
AgentRole
  -> ToolCall(name, arguments)
  -> ToolRegistry validates role permission
  -> ToolRegistry validates arguments with Pydantic schema
  -> Python tool executes
  -> ToolResult returns
  -> AgentToolTrace records summary
```

Provider-native function calling is not the core contract in Stage 1. Future OpenAI or DeepSeek function-calling adapters should translate provider tool-call JSON into the internal `ToolCall` type and pass it through the same registry.

## Tool Boundary

Each specialist agent may call only its assigned tools. The registry rejects unauthorized calls and records the failure in trace.

This prevents the Supervisor Agent from becoming a disguised all-powerful agent and keeps multi-agent responsibilities meaningful.

## Agent State

Stage 1 extends the existing `AgentState` instead of creating a parallel state model.

Retained fields:

- `session_id`
- `learning_goal`
- `course_ids`
- `plan`
- `quiz`
- `learner_answer`
- `grade`
- `next_action`
- `status`
- `tool_trace`
- `tool_call_count`

New fields:

- `agent_plan`
- `agent_trace`
- `critic_warnings`
- `current_agent_role`

The current SQLite `sessions.state_json` can carry the extended state. Structured tables should be added only when querying needs require them.

## Agent Tool Trace

Trace records should be compact and UI-friendly.

Fields:

- `sequence_no`
- `agent_role`
- `tool_name`
- `input_summary`
- `output_summary`
- `ok`
- `elapsed_ms`
- `error`
- `fallback_reason`

Trace should not store:

- Full prompts
- Full retrieved chunks
- Full learner answers
- Raw LLM responses

Full evidence remains available through citations, chunk registry, or on-demand retrieval.

## Critic Warnings

The Critic Agent produces non-blocking warnings.

Examples:

- Evidence is missing for a quiz question.
- Grade feedback references a point that was not in `expected_points`.
- Next action appears inconsistent with grade score.

A critic warning should be attached to the session response and trace, but it should not prevent a session from reaching `completed` or `waiting_for_answer`.

Hard gating can be considered after real-user acceptance data shows which warnings are reliable enough to block.

## API Strategy

Stage 1 reuses the current Study Coach Session API:

```text
POST /sessions
POST /sessions/{id}/messages
GET  /sessions/{id}
GET  /sessions/{id}/mastery
GET  /sessions/{id}/trace
```

Responses may add backward-compatible fields such as:

- `agent_plan`
- `agent_trace`
- `critic_warnings`

A future additive endpoint may be useful:

```text
GET /sessions/{id}/agent-trace
```

Stage 1 should not introduce `/multi-agent/*`.

## UI Strategy

Streamlit should still present this as Study Coach. The user does not need a separate "multi-agent product mode".

UI additions:

- Agent timeline showing the six-role sequence.
- Tool call rows showing role, tool name, success/error, latency, and summaries.
- Critic warning section in the Evidence or Coach popover.
- Clear empty states when no agent trace or warnings exist.

The UI should not expose raw prompts, raw model responses, or full chunks inside the trace timeline.

## Testing Strategy

Stage 1 needs deterministic tests for:

- Agent role definitions.
- Role allowed-tool mapping.
- ToolCall argument validation.
- Unauthorized tool calls failing with trace entries.
- Fixed role sequence.
- End-to-end Study Coach session compatibility.
- Critic warnings being recorded without blocking completion.
- API response backward compatibility.
- Streamlit formatting helpers for agent timeline and critic warnings.

The existing deterministic evaluation suite must remain offline-runnable.

## Stage 1 Acceptance Criteria

Stage 1 is complete when:

1. The same Study Coach session can run a complete learning turn.
2. Trace shows the fixed six-agent sequence: Supervisor, Retrieval, Quiz, Grader, Coach, Critic.
3. Every role tool call is validated against allowed tools.
4. Unauthorized tool calls fail and are recorded in Agent Tool Trace.
5. Critic warnings appear in API/UI but do not block `completed` or `waiting_for_answer`.
6. Existing Study Coach API contract tests still pass.
7. The deterministic evaluation remains offline-runnable.

## Stage 2 Outlook

Stage 2 can add limited LLM-assisted decisions while preserving the bounded workflow.

Candidate upgrades:

- Supervisor Agent generates plan rationale, but still chooses only predefined sequence variants.
- Retrieval Agent uses LLM-assisted query expansion or evidence-selection rationale.
- Quiz Agent and Grader Agent use stronger live adapters while preserving deterministic fallback.
- Critic Agent uses LLM-assisted consistency review while warnings remain non-blocking by default.
- Provider-native function calling adapters translate OpenAI or DeepSeek tool calls into internal `ToolCall`.
- Limited parallelism for multi-query retrieval or independent critic checks.

Stage 2 still excludes an open-ended autonomous agent swarm.

## Implementation Notes

Likely files to modify or add:

- `src/final_agent/agent/models.py`
- `src/final_agent/agent/tools.py`
- `src/final_agent/agent/roles.py`
- `src/final_agent/agent/tool_registry.py`
- `src/final_agent/agent/orchestrator.py`
- `src/final_agent/agent/critics.py`
- `src/final_agent/api/schemas.py`
- `src/final_agent/api/app.py`
- `src/final_agent/memory/models.py`
- `src/final_agent/memory/repository.py`
- `src/final_agent/ui/study_coach_view.py`
- `src/final_agent/ui/app.py`

The first implementation plan should start with types and registry tests before changing the workflow.
