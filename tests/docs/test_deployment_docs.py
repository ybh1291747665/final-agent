from __future__ import annotations

from pathlib import Path


def test_deployment_guide_documents_required_runtime_steps():
    text = Path("docs/deployment.md").read_text(encoding="utf-8")

    assert "FINAL_AGENT_ROOT" in text
    assert "DEEPSEEK_API_KEY" in text
    assert "ARK_API_KEY" in text
    assert "pip install -e \".[dev]\"" in text
    assert "final-agent api --host 127.0.0.1 --port 8000" in text
    assert "final-agent ui" in text
    assert "pytest" in text
