# Final Evidence Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the review-readiness gap by exposing promised Study Coach state in the UI, removing the remaining API test warning, and publishing a reproducible manual demo evidence package.

**Architecture:** Keep the bounded Study Coach workflow unchanged. Surface existing API state through the Streamlit UI, modernize the API test transport to remove the Starlette/httpx warning, then document one reproducible local-course happy path in README plus a dedicated evidence note.

**Tech Stack:** Python, Streamlit, FastAPI, httpx, pytest, Pydantic, SQLite, Markdown docs

---

## File Map

- Modify: `src/final_agent/api/schemas.py`
  - Extend session response shape to expose `next_action`.
- Modify: `src/final_agent/api/app.py`
  - Return `next_action` from session responses.
- Modify: `src/final_agent/ui/app.py`
  - Render mastery, next action, and an expandable ordered tool trace in Study Coach mode.
- Modify: `tests/api/test_sessions.py`
  - Replace `TestClient` usage with `httpx` ASGI transport to remove the warning.
- Create: `tests/ui/test_study_coach_rendering.py`
  - Unit-test the new Study Coach formatting helpers without requiring Streamlit browser automation.
- Modify: `README.md`
  - Add a concise evidence summary and link to the dedicated demo document.
- Modify: `DESIGN.md`
  - Update the “Next Work” / status language to reflect completed evidence work once done.
- Modify: `interviewer-note.md`
  - Log the UI evidence-gap decision, warning fix, manual demo evidence, and documentation trade-offs as they happen.
- Create: `docs/final-agent-study-coach-demo-evidence.md`
  - Hold the reproducible happy-path walkthrough, evidence excerpts, and 90-second demo script.

## Task 1: Surface `next_action` in the API contract

**Files:**
- Modify: `src/final_agent/api/schemas.py`
- Modify: `src/final_agent/api/app.py`
- Test: `tests/api/test_sessions.py`

- [ ] **Step 1: Write the failing API test**

```python
def test_session_api_contract(tmp_path):
    transport = httpx.ASGITransport(app=create_app(repository=MemoryRepository(tmp_path / "api.sqlite")))
    with httpx.Client(transport=transport, base_url="http://testserver") as client:
        created = client.post("/sessions", json={"learning_goal": "review configuration management and version control", "course_ids": ["course-a"]})
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert created.json()["next_action"] == ""

        answered = client.post(
            f"/sessions/{session_id}/messages",
            json={"message": "Version control manages revisions and branching, but I need more review on naming schemes."},
        )
        assert answered.status_code == 200
        assert answered.json()["status"] == "completed"
        assert answered.json()["next_action"] == "practice_variant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_sessions.py::test_session_api_contract -v`

Expected: FAIL because `next_action` is missing from `SessionResponse` and the API payload.

- [ ] **Step 3: Write minimal implementation**

```python
class SessionResponse(BaseModel):
    session_id: str
    status: AgentStatus
    plan: list[StudyPlanStep]
    quiz: QuizQuestion | None = None
    grade: GradeResult | None = None
    next_action: str = ""
```

```python
def _response(self, state: AgentState) -> SessionResponse:
    return SessionResponse(
        session_id=state.session_id,
        status=state.status,
        plan=state.plan,
        quiz=state.quiz,
        grade=state.grade,
        next_action=state.next_action,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_sessions.py::test_session_api_contract -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/final_agent/api/schemas.py src/final_agent/api/app.py tests/api/test_sessions.py
git commit -m "feat: expose study coach next action in api responses"
```

## Task 2: Add testable Study Coach rendering helpers and UI visibility

**Files:**
- Modify: `src/final_agent/ui/app.py`
- Test: `tests/ui/test_study_coach_rendering.py`

- [ ] **Step 1: Write the failing UI helper tests**

```python
from final_agent.ui.app import format_study_coach_summary, format_trace_lines


def test_format_study_coach_summary_includes_next_action_and_mastery():
    response = {
        "status": "completed",
        "plan": [{"objective": "Find relevant course material", "tool_name": "search_course_material", "completed": False}],
        "quiz": {"prompt": "Explain version control."},
        "grade": {"score": 0.5, "feedback": "Review naming scheme."},
        "next_action": "practice_variant",
    }
    mastery = {
        "configuration management": {"score": 0.5, "attempts": 1},
    }

    content = format_study_coach_summary(response, mastery)

    assert "**Next Action:** `practice_variant`" in content
    assert "- `configuration management`: score=0.50, attempts=1" in content


def test_format_trace_lines_orders_entries():
    trace = [
        {"sequence_no": 2, "tool_name": "generate_quiz", "ok": True, "elapsed_ms": 1, "error": ""},
        {"sequence_no": 1, "tool_name": "search_course_material", "ok": True, "elapsed_ms": 3, "error": ""},
    ]

    assert format_trace_lines(trace) == [
        "1. `search_course_material` ok in 3 ms",
        "2. `generate_quiz` ok in 1 ms",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_study_coach_rendering.py -v`

Expected: FAIL because the helper functions do not exist yet.

- [ ] **Step 3: Write minimal helper implementation**

```python
def format_study_coach_summary(response: dict, mastery: dict[str, dict] | None = None) -> str:
    plan_lines = [
        f"- [{'x' if step.get('completed') else ' '}] {step.get('objective', '')} (`{step.get('tool_name', '')}`)"
        for step in response.get("plan", [])
    ]
    quiz = response.get("quiz") or {}
    grade = response.get("grade") or {}
    mastery = mastery or {}
    mastery_lines = [
        f"- `{topic}`: score={record.get('score', 0.0):.2f}, attempts={record.get('attempts', 0)}"
        for topic, record in sorted(mastery.items())
    ] or ["- `(none yet)`"]
    return "\n".join([
        f"**Status:** `{response.get('status')}`",
        "",
        "**Plan:**",
        *plan_lines,
        "",
        f"**Question:** {quiz.get('prompt', '(none)')}",
        f"**Grade:** {grade.get('score', 'waiting')}",
        grade.get("feedback", ""),
        "",
        f"**Next Action:** `{response.get('next_action', '') or '(pending)'}`",
        "",
        "**Mastery:**",
        *mastery_lines,
    ])


def format_trace_lines(trace: list[dict]) -> list[str]:
    lines: list[str] = []
    for entry in sorted(trace, key=lambda item: item.get("sequence_no", 0)):
        status = "ok" if entry.get("ok") else "error"
        detail = f"{entry.get('sequence_no', '?')}. `{entry.get('tool_name', '')}` {status} in {entry.get('elapsed_ms', 0)} ms"
        if entry.get("error"):
            detail += f" - {entry['error']}"
        lines.append(detail)
    return lines
```

- [ ] **Step 4: Update the Study Coach UI to consume API mastery and trace**

```python
                    if not app_state.agent_session_id:
                        response = client.create_session(question, cids or [])
                        app_state.agent_session_id = response["session_id"]
                    else:
                        response = client.send_message(app_state.agent_session_id, question)

                    mastery_response = client.get_mastery(app_state.agent_session_id)
                    trace_response = client.get_trace(app_state.agent_session_id)
                    content = format_study_coach_summary(response, mastery_response.get("mastery", {}))
                    st.markdown(content)
                    with st.expander("Study Coach tool trace", expanded=False):
                        for line in format_trace_lines(trace_response.get("trace", [])):
                            st.markdown(f"- {line}")
                    app_state._add_message("assistant", content=content)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/ui/test_study_coach_rendering.py tests/ui/test_agent_client.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/final_agent/ui/app.py tests/ui/test_study_coach_rendering.py
git commit -m "feat: surface mastery and trace in study coach ui"
```

## Task 3: Remove the FastAPI/Starlette test warning

**Files:**
- Modify: `tests/api/test_sessions.py`

- [ ] **Step 1: Write the warning-targeted failing check**

```bash
$env:PYTHONPATH='src'; pytest tests/api/test_sessions.py -q -W default
```

Expected: PASS with a warnings summary that includes `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`.

- [ ] **Step 2: Replace `TestClient` with `httpx` ASGI transport**

```python
import httpx


def test_session_api_contract(tmp_path):
    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    with httpx.Client(transport=transport, base_url="http://testserver") as client:
        created = client.post("/sessions", json={"learning_goal": "review configuration management and version control", "course_ids": ["course-a"]})
        ...
```

```python
def test_session_api_returns_conflict_for_answer_before_question(tmp_path):
    app = create_app(repository=MemoryRepository(tmp_path / "api.sqlite"))
    transport = httpx.ASGITransport(app=app)
    with httpx.Client(transport=transport, base_url="http://testserver") as client:
        response = client.post("/sessions/missing/messages", json={"message": "hello"})
        assert response.status_code == 404
```

- [ ] **Step 3: Run the warning check again**

Run: `$env:PYTHONPATH='src'; pytest tests/api/test_sessions.py -q -W default`

Expected: PASS with no warning summary.

- [ ] **Step 4: Commit**

```bash
git add tests/api/test_sessions.py
git commit -m "test: remove deprecated study coach api test client"
```

## Task 4: Record decisions in `interviewer-note.md` during implementation

**Files:**
- Modify: `interviewer-note.md`

- [ ] **Step 1: Add the UI evidence-gap entry**

```markdown
### Issue: Study Coach UI 缺少 mastery / next action / tool trace 证据字段

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `src/final_agent/ui/app.py`
- **Symptom:** 手工 demo 前，UI 只显示 status、plan、question、grade，和 Phase 7 承诺不完全一致。
- **Root cause:** Session API 已提供或可补齐相关状态，但 Streamlit Study Coach 面板未拉取 mastery/trace，也未显示 next action。
- **Options considered:**
  - Option A: 直接录 demo，在文档里解释 UI 省略字段。
  - Option B: 先补 UI 可见性，再录 demo。
- **Decision:** 选择 Option B，先让 UI 与 evidence promise 对齐。
- **Fix:** 新增 Study Coach summary/trace helpers，并展示 mastery、next action、tool trace。
- **Verification:** `pytest tests/ui/test_study_coach_rendering.py tests/ui/test_agent_client.py -v`
- **Result:** UI 证据字段齐备，可用于手工 walkthrough。
- **Resume impact:** none
```

- [ ] **Step 2: Add the warning-fix entry**

```markdown
### Issue: FastAPI/Starlette Study Coach API 测试存在第三方弃用 warning

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `tests/api/test_sessions.py`
- **Symptom:** `pytest tests/api tests/ui -q -W default` 输出 `StarletteDeprecationWarning`，影响 Draft PR review cleanliness。
- **Root cause:** 测试依赖 `fastapi.testclient.TestClient`，其底层组合已被上游标记为弃用。
- **Options considered:**
  - Option A: 在 evidence 文档中接受 warning。
  - Option B: 改用 `httpx` ASGI transport，保留同样的 API contract coverage。
- **Decision:** 选择 Option B，优先清理 review 噪音。
- **Fix:** API 测试改为 `httpx` ASGI transport。
- **Verification:** `$env:PYTHONPATH='src'; pytest tests/api/test_sessions.py -q -W default`
- **Result:** 测试通过且 warning 消失。
- **Resume impact:** none
```

- [ ] **Step 3: Commit**

```bash
git add interviewer-note.md
git commit -m "docs: log study coach evidence package decisions"
```

## Task 5: Capture the manual demo and publish evidence

**Files:**
- Create: `docs/final-agent-study-coach-demo-evidence.md`
- Modify: `README.md`
- Modify: `DESIGN.md`
- Modify: `interviewer-note.md`

- [ ] **Step 1: Run the manual demo path and capture outputs**

Run:

```bash
$env:PYTHONPATH='src'
python - <<'PY'
from final_agent.api.app import AgentService
from final_agent.memory.repository import MemoryRepository
from pathlib import Path

repo = MemoryRepository(Path("data/learner_memory.sqlite"))
service = AgentService(repo)
created = service.create_session(type("Payload", (), {"learning_goal": "review configuration management and version control", "course_ids": ["course-a"]})())
print(created.model_dump())
answered = service.send_message(created.session_id, "Version control manages revisions and branching, but I still need review on naming schemes.")
print(answered.model_dump())
print(repo.get_mastery(created.session_id))
print(repo.list_trace(created.session_id))
PY
```

Expected:

- first response has `waiting_for_answer`
- second response has `completed`
- `next_action` is `practice_variant`
- mastery contains one topic with a mid-band score
- trace contains ordered tool calls including `search_course_material`, `generate_quiz`, `grade_answer`, `update_mastery`

- [ ] **Step 2: Write the dedicated evidence doc**

```markdown
# Study Coach Demo Evidence

## Demo setup

- Local data source: `data/markdown`
- Learner goal: `review configuration management and version control`
- Learner answer: `Version control manages revisions and branching, but I still need review on naming schemes.`

## Happy-path walkthrough

1. Start the FastAPI Study Coach service and Streamlit UI.
2. Open Study Coach mode.
3. Enter the learner goal above.
4. Confirm the UI shows a generated question and a waiting state.
5. Submit the learner answer above.
6. Confirm the UI shows grading feedback, a mid-band mastery update, `practice_variant`, and an ordered tool trace.

## Evidence excerpts

- Session status before answer: `waiting_for_answer`
- Session status after answer: `completed`
- Next action: `practice_variant`

## Known limitations of this demo

- `generate_quiz` is deterministic in v1.
- `grade_answer` is expected-point based in v1.
- This demo proves integration and persistence, not live LLM quality.

## 90-second demo script

`final-agent` still presents itself as a RAG-powered study assistant, but this branch adds a bounded Study Coach loop on top of the knowledge layer. Here I enter a review goal on configuration management and version control. The app creates a short plan, retrieves course material, and generates a quiz question. After I answer, the backend grades expected-point coverage, updates SQLite mastery, and recommends the next action as `practice_variant` because the answer is only partially complete. The UI now exposes the same evidence we need for review: the current mastery score and the ordered tool trace for the run.
```

- [ ] **Step 3: Update README and DESIGN**

```markdown
## Evidence

See `docs/final-agent-study-coach-demo-evidence.md` for the manual Study Coach walkthrough, example mastery update, ordered tool trace, and demo script.
```

```markdown
## Next Work

Recommended next steps after the evidence package:

1. Replace deterministic quiz generation with a live adapter while keeping the current offline baseline.
2. Replace deterministic grading with a live adapter while keeping regression coverage.
3. Persist retrieved context in agent state so future live quiz/grading stays grounded in course material.
```

- [ ] **Step 4: Add the final evidence entry to `interviewer-note.md`**

```markdown
### Issue: Study Coach final evidence package 收口

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `README.md`, `DESIGN.md`, `docs/final-agent-study-coach-demo-evidence.md`
- **Symptom:** 仓库已有代码和离线评测，但缺少一条可复现的手工 walkthrough、example trace 与 demo 脚本。
- **Root cause:** 先前工作优先把 bounded workflow 与 offline evaluation 做完，证据文档尚未单独整理。
- **Options considered:**
  - Option A: 只在 README 追加长段说明。
  - Option B: README 保持高层摘要，细节单独放到 `docs/final-agent-study-coach-demo-evidence.md`。
- **Decision:** 选择 Option B，形成双层 evidence 发布结构。
- **Fix:** 记录本地课件 happy path、mastery 结果、ordered trace、90 秒 demo script，并在 README 中加入入口链接。
- **Verification:** 人工核对文档与实际 API / UI 输出一致。
- **Result:** Draft PR 具备可 review 的手工 demo 证据路径。
- **Resume impact:** can mention bounded workflow evidence, still no live LLM quality claim
```

- [ ] **Step 5: Commit**

```bash
git add README.md DESIGN.md interviewer-note.md docs/final-agent-study-coach-demo-evidence.md
git commit -m "docs: publish study coach demo evidence"
```

## Task 6: Final verification

**Files:**
- Verify repository state only

- [ ] **Step 1: Run focused regression checks**

Run: `$env:PYTHONPATH='src'; pytest tests/api/test_sessions.py tests/ui/test_agent_client.py tests/ui/test_study_coach_rendering.py -v`

Expected: PASS

- [ ] **Step 2: Run lint**

Run: `$env:PYTHONPATH='src'; python -m ruff check src tests`

Expected: PASS

- [ ] **Step 3: Run full test and coverage verification**

Run: `$env:PYTHONPATH='src'; pytest --cov=final_agent --cov-report=term-missing`

Expected: PASS with coverage report emitted.

- [ ] **Step 4: Run final evaluation**

Run: `$env:PYTHONPATH='src'; python -m final_agent.evaluation.runner --suite agent-final --data-dir data`

Expected: JSON report emitted to `data/evaluation/agent-final.json`.

- [ ] **Step 5: Commit final cleanups if needed**

```bash
git status --short
```

Expected: clean working tree or only intentional uncommitted user changes.
