# final-agent Context

`final-agent` is a local-first study assistant built around course material, retrieval-grounded generation, and bounded learning workflows. This glossary defines the project-specific language used when designing its agent and knowledge workflows.

## Language

**Multi-Agent Study Coach**:
A bounded learning workflow where fixed-role agents collaborate to help a learner review course material, answer questions, receive grading, and choose a next study action.
_Avoid_: Generic autonomous agent platform, open-ended agent swarm

**Bounded Agent Workflow**:
An agent workflow whose roles, tools, transitions, and stopping conditions are explicit and testable.
_Avoid_: Fully autonomous self-governing agent

**Agent State**:
The persisted study-session state that carries the learning goal, course scope, plan, quiz, learner answer, grade, next action, trace, and multi-agent additions.
_Avoid_: Parallel session state, separate multi-agent state store

**Study Coach Session API**:
The stable FastAPI session contract used by the UI to create, continue, inspect, and trace Study Coach sessions.
_Avoid_: Separate multi-agent API namespace

**Multi-Agent Execution Skeleton**:
The first implementation stage that introduces roles, typed tool calls, role-level tool boundaries, sequential orchestration, agent trace, critic warnings, and UI visibility without LLM-autonomous planning.
_Avoid_: Full autonomous multi-agent runtime

**AI/RAG Study Coach Positioning**:
The project framing that emphasizes retrieval-grounded learning assistance, evidence use, multi-agent learning roles, and measurable study outcomes.
_Avoid_: Infrastructure-first platform story, generic chatbot demo

**Course Review Coach**:
The learner-facing product shape where the system helps a learner review course material through grounded explanation, targeted quiz questions, feedback, and next study actions.
_Avoid_: Exam proctor, generic quiz app, open-ended tutor

**Learning Goal Entry**:
The Study Coach entry pattern where a learner starts with a natural-language learning goal plus an optional course scope, and the system derives the review path from retrieved course material.
_Avoid_: Mandatory chapter picker, fixed quiz selection, manual topic tree navigation

**Single-Question Review Turn**:
A review turn that produces one grounded quiz question, accepts one learner answer, and returns one grade with one next study action.
_Avoid_: Batch quiz session, exam paper, multi-question assessment

**Evidence-Based Feedback**:
Feedback that explains a learner's answer using retrieved course material, naming what was covered and what should be reviewed next.
_Avoid_: Generic encouragement, unsupported grading rationale

**Citation-Aware Evidence Panel**:
The inspection surface where technical evidence identifiers and source chunks are shown separately from learner-facing feedback.
_Avoid_: Chunk IDs in primary feedback, hidden evidence chain

**Evidence Snapshot**:
A compact evidence record persisted through Agent State and API responses with chunk identity, source, and summary, while full chunk text remains a transient input for grading and generation.
_Avoid_: Full chunk payload in session state, raw retrieval transcript, evidence-free session response

**Top-3 Evidence Set**:
The evidence selection rule where each review turn carries at most three compact evidence snapshots into the learner-facing response and inspection surfaces.
_Avoid_: Exhaustive retrieval dump, single-source-only evidence

**Fixed Sequential Collaboration**:
A multi-agent collaboration pattern where fixed-role agents run in a predetermined order for the first version of a workflow.
_Avoid_: Dynamic free-form orchestration, parallel-first agent routing

**Supervisor Agent**:
The role that owns the study turn plan and coordinates the fixed sequence of specialist agents.
_Avoid_: Autonomous planner, free-form router

**Retrieval Agent**:
The role that finds course-grounded material and prepares evidence for downstream agents.
_Avoid_: Search helper, knowledge fetcher

**Quiz Agent**:
The role that creates a learner-facing quiz from the current goal and retrieved course evidence.
_Avoid_: Question generator tool

**Grader Agent**:
The role that evaluates the learner answer against expected points and available course evidence.
_Avoid_: Scoring function

**Coach Agent**:
The role that updates mastery and chooses the learner's next study action.
_Avoid_: Advisor, recommender

**Critic Agent**:
The role that checks whether the evidence, grading, and next action are internally consistent before the response is returned.
_Avoid_: Reflection agent, self-critic swarm

**Critic Warning**:
A non-blocking finding produced by the Critic Agent to explain possible evidence, grading, or next-action inconsistencies.
_Avoid_: Hard rejection, automatic retry trigger

**Tool Boundary**:
The rule that each agent role may call only the tools assigned to that role, while the Supervisor Agent coordinates without directly calling business tools.
_Avoid_: Shared global tool access, supervisor-as-everything

**Internal Typed Tool Calling**:
The project-owned protocol where an agent emits a typed `ToolCall`, the registry validates role permissions and arguments, and execution returns a typed `ToolResult`.
_Avoid_: Provider-native function calling as the core contract

**Agent Tool Trace**:
A compact record of which agent called which tool, with summarized inputs and outputs, timing, success state, and fallback reason.
_Avoid_: Full prompt log, full chunk log, raw model transcript
