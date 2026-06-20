from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def sample_chunks():
    from final_agent.schemas import Chunk, ScoredChunk

    a = Chunk(chunk_id="aaaabbbb1111", doc_id="doc-a", course_id="devsecops", text="DevSecOps uses automation.", heading_path=["Intro"], char_start=0, char_end=24)
    b = Chunk(chunk_id="ccccdddd2222", doc_id="doc-a", course_id="devsecops", text="CI pipelines run tests.", heading_path=["Intro"], char_start=25, char_end=47)
    c = Chunk(chunk_id="eeeeffff3333", doc_id="doc-b", course_id="git", text="Version control protects changes.", heading_path=["Git"], char_start=0, char_end=33)
    return [ScoredChunk(chunk=a, score=0.9, source="fixture"), ScoredChunk(chunk=b, score=0.7, source="fixture"), ScoredChunk(chunk=c, score=0.5, source="fixture")]
