# final-agent Deployment Guide

This guide captures the local deployment path for the current Streamlit + FastAPI architecture.

## 1. Runtime Requirements

- Python 3.11
- Conda or another Python virtual environment manager
- Local disk write access for `data/`
- Optional GPU support for embedding/reranker models

## 2. Environment Variables

Create `.env` in the project root.

```bash
FINAL_AGENT_ROOT=E:/githubitem/final-agent
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
ARK_API_KEY=...
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
FINAL_AGENT_API_BASE_URL=http://127.0.0.1:8000
```

`DEEPSEEK_API_KEY` is required for answer generation. `ARK_API_KEY` is required only when Doubao PDF parsing is enabled.

## 3. Install

```bash
conda create -n final-agent python=3.11 -y
conda activate final-agent
pip install -e ".[dev]"
```

## 4. Startup Order

Start the Study Coach API first:

```bash
final-agent api --host 127.0.0.1 --port 8000
```

Then start the Streamlit UI in a second terminal:

```bash
final-agent ui
```

The main RAG modes can run inside Streamlit with local modules. Study Coach uses `AgentApiClient -> FastAPI -> agent workflow -> SQLite`, so the API should be running before using that mode.

Check service readiness:

```bash
curl http://127.0.0.1:8000/health
```

## 5. Verification

```bash
pytest tests/test_schemas.py tests/retrieval tests/ingestion -v
pytest tests/evaluation tests/agent tests/memory tests/api tests/ui -v
ruff check src tests
python -m final_agent.evaluation.runner --suite agent-final --data-dir data
```

## 6. Operational Notes

- Course creation, course selection, upload ownership, and empty-course deletion are managed in the Streamlit sidebar.
- Re-uploading an unchanged document uses the metadata content signature to skip embedding, vector writes, and course index rebuild.
- Course knowledge maintenance repairs one selected course at a time by migrating legacy dense chunks and rebuilding the course BM25 snapshot.
- Runtime metrics are available in the Streamlit sidebar under `Runtime metrics`.
- Metrics are in-process and reset when the Python process restarts.
- If repair fails, close other processes that may hold vector store or snapshot files, then retry the current course repair.
