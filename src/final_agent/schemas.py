"""Shared data models used across ingestion / knowledge / retrieval / generation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A semantic chunk extracted from a document."""

    chunk_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    doc_id: str = ""
    course_id: str = ""
    text: str = ""
    heading_path: list[str] = Field(default_factory=list)
    page_num: Optional[int] = None
    char_start: int = 0
    char_end: int = 0
    metadata: dict = Field(default_factory=dict)


class ScoredChunk(BaseModel):
    """A chunk paired with a retrieval score."""

    chunk: Chunk
    score: float
    source: str = ""  # "dense" | "sparse" | "rrf" | "rerank"


class ReadingContext(BaseModel):
    """Optional document position used as a bounded retrieval prior."""

    doc_id: str = ""
    page_num: Optional[int] = Field(default=None, ge=1)
    page_boost_enabled: bool = True


class GeneratedAnswer(BaseModel):
    """Raw LLM output with extracted citations."""

    answer: str
    citations: list[str] = Field(default_factory=list)  # list of chunk_id
    model: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class HallucinationFlag(BaseModel):
    """A sentence flagged as potentially hallucinated."""

    sentence: str
    cited_chunk_id: str
    similarity_score: float
    flagged: bool


class VerifiedAnswer(BaseModel):
    """Generated answer after hallucination guard check."""

    raw_answer: str
    flags: list[HallucinationFlag] = Field(default_factory=list)
    is_clean: bool = True  # True if no flags raised
    verified_at: datetime = Field(default_factory=datetime.now)
