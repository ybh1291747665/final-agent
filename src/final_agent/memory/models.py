from __future__ import annotations

from pydantic import BaseModel


class MasterySnapshot(BaseModel):
    topic: str
    score: float
    attempts: int
