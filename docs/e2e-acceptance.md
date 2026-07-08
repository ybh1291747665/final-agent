# final-agent E2E Acceptance Runbook

Use this checklist before demo or local deployment handoff.

## 1. Start Services

Terminal 1:

```bash
final-agent api --host 127.0.0.1 --port 8000
```

Confirm API readiness:

```bash
curl http://127.0.0.1:8000/health
```

Terminal 2:

```bash
final-agent ui
```

## 2. Upload Course Material

1. Open the Streamlit UI.
2. Create or select a course in the sidebar.
3. Confirm the upload ownership text shows the selected course.
4. Upload a PDF or Markdown file with `Upload`.
5. Confirm the knowledge base document list shows the new document and chunk count.
6. Upload the same unchanged file again.
7. Confirm the UI reports no changes and skips rebuild.

## 3. Ask And Evidence

1. Select `Ask`.
2. Ask a course-specific question.
3. Confirm the answer includes citations.
4. Open `Evidence`.
5. Confirm the Evidence summary reports how many chunks are cited and which retrieval sources contributed.
6. Confirm cited chunks show source, score, heading, and text.
7. Open `Validation`.
8. Confirm the Validation summary reports passed checks and items needing review.
9. Confirm semantic validation is present, or the UI clearly states no validation data exists.
10. Confirm RAG citations in the main answer use file name and page labels instead of raw chunk IDs when page metadata is available.

## 4. Study Coach

1. Start the FastAPI service before using this mode.
2. Select `Study Coach`.
3. Enter a learning goal.
4. Confirm a quiz is created and the session waits for an answer.
5. Submit an answer.
6. Confirm the Coach summary names the current phase.
7. Confirm grade, mastery, lowest-mastery snapshot, next action, and trace are visible.
8. Open `Multi-Agent timeline`.
9. Confirm the timeline includes Supervisor, Retrieval, Quiz, Grader, Coach, and Critic in order after a complete turn.
10. Open `Critic warnings`.
11. Confirm warnings are visible when present and the session can still complete.
12. Open `Study Coach evidence`.
13. Confirm the turn shows at most top 3 evidence snapshots.
14. Confirm evidence entries show file name and page when page metadata is available.
15. Confirm the session remains a single-question review turn: one question, one answer, one grade, and one next action.
16. Confirm grading feedback is evidence-based feedback rather than generic encouragement.

## 5. Maintenance And Monitoring

1. Run current course repair from the course knowledge maintenance panel.
2. Confirm success text reports migrated and rebuilt chunks.
3. Open `Runtime metrics`.
4. Confirm retrieval and model-call counters update after Ask or Study Coach activity.

Acceptance passes when Upload, Ask, Evidence, Validation, Study Coach, `/health`, and Runtime metrics all work in one local run.
