from __future__ import annotations

import re
from itertools import cycle, islice
from pathlib import Path

from final_agent.evaluation.models import EvaluationCase
from final_agent.ingestion.chunker import chunk_markdown
from final_agent.schemas import Chunk


def load_cases() -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for i in range(10):
        cases.append(EvaluationCase(
            case_id=f"retrieval-{i + 1:02d}",
            category="retrieval",
            course_ids=["fixture-course"],
            user_input=f"Find concept {i + 1}",
            expected_tools=["search_course_material"],
            required_citations=[f"fixture-{i + 1:02d}"],
            expected_outcome="Retrieve a grounded course-material answer.",
        ))
    for i in range(10):
        cases.append(EvaluationCase(
            case_id=f"tool-{i + 1:02d}",
            category="tool_selection",
            course_ids=["fixture-course"],
            user_input=f"Create a quiz for topic {i + 1}",
            expected_tools=["search_course_material", "generate_quiz"],
            expected_outcome="Select the retrieval and quiz tools in order.",
        ))
    for i in range(10):
        cases.append(EvaluationCase(
            case_id=f"adaptive-{i + 1:02d}",
            category="adaptive_review",
            course_ids=["fixture-course"],
            user_input=f"Grade answer for topic {i + 1}",
            expected_tools=["grade_answer", "update_mastery"],
            expected_outcome="Grade the learner answer and update mastery.",
            expected_score_band="high" if i % 2 == 0 else "medium",
        ))
    return cases


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "doc"


def load_local_chunks(data_dir: str | Path = "data") -> list[Chunk]:
    chunks: list[Chunk] = []
    markdown_root = Path(data_dir) / "markdown"
    if not markdown_root.exists():
        return chunks

    for md_path in sorted(markdown_root.rglob("*.md")):
        doc_id = _slug(md_path.parent.name if md_path.parent != markdown_root else md_path.stem)
        try:
            doc_chunks = chunk_markdown(md_path, doc_id=doc_id)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        for index, chunk in enumerate(doc_chunks, start=1):
            if len(chunk.text.strip()) < 30:
                continue
            chunk.chunk_id = f"{doc_id}-{index:03d}"
            chunk.course_id = doc_id
            chunks.append(chunk)
    return chunks


def load_local_rag_cases(data_dir: str | Path = "data", target_count: int = 30) -> list[EvaluationCase]:
    chunks = load_local_chunks(data_dir)
    if not chunks:
        return []

    selected = list(islice(cycle(chunks), target_count))
    cases: list[EvaluationCase] = []
    for index, chunk in enumerate(selected, start=1):
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else chunk.text[:60]
        if index <= target_count // 3:
            category = "retrieval"
            expected_tools = ["search_course_material", "generate_quiz"]
            band = None
            prefix = "local-retrieval"
        elif index <= (target_count // 3) * 2:
            category = "tool_selection"
            expected_tools = ["search_course_material", "generate_quiz"]
            band = None
            prefix = "local-tool"
        else:
            category = "adaptive_review"
            expected_tools = ["search_course_material", "generate_quiz", "grade_answer", "update_mastery"]
            band = "high"
            prefix = "local-adaptive"
        cases.append(EvaluationCase(
            case_id=f"{prefix}-{index:02d}",
            category=category,
            course_ids=[chunk.course_id],
            user_input=f"Review {heading}",
            expected_tools=expected_tools,
            required_citations=[chunk.chunk_id],
            expected_outcome=f"Use material from {chunk.doc_id}.",
            expected_score_band=band,
        ))
    return cases
