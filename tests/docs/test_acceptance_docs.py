from __future__ import annotations

from pathlib import Path


def test_acceptance_runbook_covers_real_user_e2e_flow():
    text = Path("docs/e2e-acceptance.md").read_text(encoding="utf-8")

    assert "final-agent api --host 127.0.0.1 --port 8000" in text
    assert "final-agent ui" in text
    assert "Upload" in text
    assert "Ask" in text
    assert "Study Coach" in text
    assert "Evidence" in text
    assert "Validation" in text
    assert "/health" in text


def test_acceptance_runbook_covers_multi_agent_stage_one_flow():
    text = Path("docs/e2e-acceptance.md").read_text(encoding="utf-8")

    assert "Multi-Agent timeline" in text
    assert "Supervisor" in text
    assert "Retrieval" in text
    assert "Quiz" in text
    assert "Grader" in text
    assert "Coach" in text
    assert "Critic" in text
    assert "Critic warnings" in text


def test_acceptance_runbook_covers_evidence_carrying_review_turn():
    text = Path("docs/e2e-acceptance.md").read_text(encoding="utf-8")

    assert "Study Coach evidence" in text
    assert "top 3" in text
    assert "file name and page" in text
    assert "single-question review turn" in text
    assert "evidence-based feedback" in text
