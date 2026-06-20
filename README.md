# final-agent

`final-agent` is a RAG-powered study assistant with an experimental adaptive study coach layer.

The existing knowledge layer ingests PDF or Markdown course material, chunks it with page awareness, builds dense and BM25 indexes, retrieves with hybrid search and RRF, reranks results, generates citation-grounded answers, and checks cited sentences for semantic consistency.

The new study coach layer adds typed tools, deterministic planning, a bounded study workflow, persistent learner memory, a FastAPI session API, and a fixture-backed evaluation harness. The project title should remain **RAG-Powered Study Assistant** until the live Agent workflow has been demonstrated with real course material and documented final evidence.

## Current Capabilities

- PDF and Markdown ingestion.
- Doubao VLM PDF-to-Markdown parsing.
- Page-aware Markdown chunking.
- ChromaDB dense vector storage.
- BM25 sparse index persistence.
- Dense + sparse retrieval with RRF fusion.
- Cross-encoder reranking when `sentence-transformers` is installed.
- Citation-grounded answer generation.
- Semantic hallucination checks.
- Course filtering.
- Five existing RAG study modes in Streamlit.
- Typed study coach contracts and tools.
- Deterministic quiz generation and keyword/expected-point grading for v1.
- SQLite learner memory and ordered tool traces.
- FastAPI session endpoints for study coach sessions.
- Fixed 30-case evaluation harness.

## Architecture

```text
Streamlit UI
    -> FastAPI Agent Service
        -> Bounded Study Workflow
            -> search_course_material
            -> summarize_course
            -> generate_quiz
            -> grade_answer
            -> get_learning_profile
            -> update_mastery
        -> Existing RAG Pipeline
        -> SQLite Learner Memory + Tool Trace Store
```

## Setup

```bash
conda create -n final-agent python=3.11 -y
conda activate final-agent
pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with the API keys needed for real PDF parsing and LLM generation. Unit tests are designed to run without API keys, model downloads, ChromaDB data, or network calls.

## Usage

```bash
final-agent ingest lecture.pdf
final-agent ask "How should I understand CI automation?"
final-agent review "configuration management"
final-agent api --host 127.0.0.1 --port 8000
final-agent ui
```

Study coach API:

```text
POST /sessions
POST /sessions/{id}/messages
GET  /sessions/{id}
GET  /sessions/{id}/mastery
GET  /sessions/{id}/trace
```

## Evaluation

The repository includes a fixed 30-case fixture harness:

```bash
python -m final_agent.evaluation.runner --suite baseline
python -m final_agent.evaluation.runner --suite agent-final
```

Latest generated fixture report: `data/evaluation/agent-final.json`.

Measured fixture results:

| Metric | Value |
|---|---:|
| Total cases | 30 |
| Task completion rate | 100% |
| Tool-selection accuracy | 33.3% |
| Citation-grounding rate | 100% |
| Grading agreement | 50% |
| Error rate | 0% |

These are deterministic fixture-harness results, not live model quality claims. Citation grounding is fixture-derived in this harness; do not use it as production accuracy or latency evidence.

## Verification

```bash
pytest tests/test_schemas.py tests/retrieval tests/ingestion -v
pytest tests/evaluation tests/agent tests/memory tests/api tests/ui -v
ruff check src tests
pytest --cov=final_agent --cov-report=term-missing
python -m final_agent.evaluation.runner --suite agent-final
```

## Known Limitations

- The v1 planner is deterministic and rule-based.
- The v1 grader uses expected-point keyword coverage rather than LLM judgment.
- The evaluation harness uses small fixed fixtures, not the full local course database.
- Real retrieval, reranking, PDF parsing, and generation still require their configured dependencies and API keys.
