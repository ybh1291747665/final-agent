# final-agent Study Coach Demo Evidence

## Demo Setup

- Execution environment: `conda` environment `final-agent`
- Install command: `conda run -n final-agent python -m pip install -e ".[dev]"`
- Data source: local course files under `data/markdown`
- API path exercised: `POST /sessions`, `POST /sessions/{id}/messages`, `GET /sessions/{id}/mastery`, `GET /sessions/{id}/trace`
- Learner goal: `review configuration management and version control`
- Learner answer: `Configuration management controls revisions, but I still need help with branching.`

This walkthrough demonstrates real `FastAPI -> study workflow -> SQLite memory` integration with local course data loaded through the existing knowledge layer. It does not claim live LLM-backed quiz generation or grading.

## Happy Path

1. Start the Study Coach API inside the `final-agent` conda environment.
2. Open the Streamlit UI and switch to `Study Coach` mode.
3. Enter the learner goal `review configuration management and version control`.
4. Confirm the first response reaches `waiting_for_answer`, shows a generated question, and records an initial tool trace.
5. Submit the learner answer `Configuration management controls revisions, but I still need help with branching.`
6. Confirm the run reaches `completed`, returns grading feedback, updates mastery, and chooses `practice_variant` as the next action.
7. Expand the tool trace and confirm the ordered calls are:
   - `search_course_material`
   - `generate_quiz`
   - `grade_answer`
   - `update_mastery`

## API Evidence Excerpts

Observed `POST /sessions` response excerpt:

```json
{
  "status": "waiting_for_answer",
  "quiz": {
    "topic": "review configuration management and version control",
    "prompt": "Explain review configuration management and version control and mention: review, configuration, management."
  },
  "next_action": ""
}
```

Observed `POST /sessions/{id}/messages` response excerpt:

```json
{
  "status": "completed",
  "grade": {
    "score": 0.6666666666666666,
    "covered_points": ["configuration", "management"],
    "missed_points": ["review"],
    "feedback": "Review: review"
  },
  "next_action": "practice_variant"
}
```

Observed `GET /sessions/{id}/mastery` response excerpt:

```json
{
  "mastery": {
    "review configuration management and version control": {
      "score": 0.6666666666666666,
      "attempts": 1
    }
  }
}
```

Observed `GET /sessions/{id}/trace` response excerpt:

```json
{
  "trace": [
    {
      "sequence_no": 1,
      "tool_name": "search_course_material",
      "ok": true,
      "elapsed_ms": 12772
    },
    {
      "sequence_no": 2,
      "tool_name": "generate_quiz",
      "ok": true,
      "elapsed_ms": 0
    },
    {
      "sequence_no": 3,
      "tool_name": "grade_answer",
      "ok": true,
      "elapsed_ms": 0
    },
    {
      "sequence_no": 4,
      "tool_name": "update_mastery",
      "ok": true,
      "elapsed_ms": 8
    }
  ]
}
```

## What This Proves

- The Study Coach API can create a session, pause for an answer, resume, grade, persist mastery, and finish.
- The FastAPI path now warms the BM25 cache on startup so the first retrieval step succeeds in the same process.
- The UI can surface the same evidence that the API exposes: question, grade, next action, mastery, and ordered tool trace.
- The local evidence path is reproducible inside the documented `conda` environment.

## Known Limitations Of This Demo

- `generate_quiz` is deterministic in v1 and derives expected points from the learner goal text.
- `grade_answer` is deterministic in v1 and scores keyword/expected-point coverage rather than LLM judgment.
- The demo proves workflow integration and persistence, not live LLM quality.
- Real retrieval, reranking, PDF parsing, and generation still depend on the configured runtime dependencies and any required API keys.

## 90-Second Demo Script

`final-agent` still presents itself as a RAG-powered study assistant, but this branch adds a bounded Study Coach loop on top of the existing knowledge layer. Here I enter a review goal on configuration management and version control. The app creates a short plan, runs retrieval through the local course corpus, and generates a deterministic quiz question. After I submit a partially correct answer, the backend grades expected-point coverage, stores the attempt in SQLite, updates mastery to a mid-band score, and recommends `practice_variant` as the next action. The UI now surfaces the same artifacts we need for review and interviews: grading feedback, mastery state, and an ordered tool trace showing the exact workflow that ran.
