from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, select
from sqlalchemy.engine import Engine

from final_agent.agent.mastery import update_mastery_score
from final_agent.agent.models import AgentState, GradeResult, MasteryRecord, QuizQuestion, ToolTraceEntry


metadata = MetaData()

sessions = Table(
    "sessions", metadata,
    Column("id", String, primary_key=True),
    Column("learning_goal", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("state_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

mastery = Table(
    "mastery", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String, ForeignKey("sessions.id"), nullable=False),
    Column("topic", String, nullable=False),
    Column("score", Float, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("updated_at", String, nullable=False),
    UniqueConstraint("session_id", "topic"),
)

quiz_attempts = Table(
    "quiz_attempts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String, ForeignKey("sessions.id"), nullable=False),
    Column("question_id", String, nullable=False),
    Column("topic", String, nullable=False),
    Column("answer", Text, nullable=False),
    Column("score", Float, nullable=False),
    Column("feedback", Text, nullable=False),
    Column("created_at", String, nullable=False),
)

tool_traces = Table(
    "tool_traces", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String, ForeignKey("sessions.id"), nullable=False),
    Column("sequence_no", Integer, nullable=False),
    Column("tool_name", String, nullable=False),
    Column("input_summary", Text, nullable=False),
    Column("ok", Boolean, nullable=False),
    Column("elapsed_ms", Integer, nullable=False),
    Column("error", Text, nullable=False),
    Column("created_at", String, nullable=False),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryRepository:
    def __init__(self, path: str | Path = "data/learner_memory.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(f"sqlite:///{self.path}")
        metadata.create_all(self.engine)

    def create_session(self, state: AgentState) -> AgentState:
        now = _now()
        with self.engine.begin() as conn:
            conn.execute(sessions.insert().values(
                id=state.session_id,
                learning_goal=state.learning_goal,
                status=state.status,
                state_json=state.model_dump_json(),
                created_at=now,
                updated_at=now,
            ))
        return state

    def save_session(self, state: AgentState) -> None:
        with self.engine.begin() as conn:
            conn.execute(sessions.update().where(sessions.c.id == state.session_id).values(
                status=state.status,
                state_json=state.model_dump_json(),
                updated_at=_now(),
            ))

    def get_session(self, session_id: str) -> AgentState:
        with self.engine.begin() as conn:
            row = conn.execute(select(sessions).where(sessions.c.id == session_id)).mappings().first()
        if row is None:
            raise KeyError(session_id)
        return AgentState.model_validate_json(row["state_json"])

    def save_attempt(self, session_id: str, quiz: QuizQuestion, answer: str, grade: GradeResult) -> None:
        with self.engine.begin() as conn:
            conn.execute(quiz_attempts.insert().values(
                session_id=session_id,
                question_id=quiz.question_id,
                topic=quiz.topic,
                answer=answer,
                score=grade.score,
                feedback=grade.feedback,
                created_at=_now(),
            ))

    def upsert_mastery(self, session_id: str, topic: str, latest_score: float) -> MasteryRecord:
        with self.engine.begin() as conn:
            row = conn.execute(select(mastery).where(mastery.c.session_id == session_id, mastery.c.topic == topic)).mappings().first()
            if row is None:
                score = latest_score
                attempts = 1
                conn.execute(mastery.insert().values(session_id=session_id, topic=topic, score=score, attempts=attempts, updated_at=_now()))
            else:
                score = update_mastery_score(float(row["score"]), latest_score)
                attempts = int(row["attempts"]) + 1
                conn.execute(mastery.update().where(mastery.c.id == row["id"]).values(score=score, attempts=attempts, updated_at=_now()))
        return MasteryRecord(topic=topic, score=score, attempts=attempts)

    def get_mastery(self, session_id: str) -> dict[str, MasteryRecord]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(mastery).where(mastery.c.session_id == session_id)).mappings().all()
        return {row["topic"]: MasteryRecord(topic=row["topic"], score=row["score"], attempts=row["attempts"]) for row in rows}

    def append_trace(self, session_id: str, trace: ToolTraceEntry) -> ToolTraceEntry:
        with self.engine.begin() as conn:
            current = conn.execute(select(tool_traces.c.sequence_no).where(tool_traces.c.session_id == session_id).order_by(tool_traces.c.sequence_no.desc())).first()
            sequence_no = (current[0] + 1) if current else 1
            conn.execute(tool_traces.insert().values(
                session_id=session_id,
                sequence_no=sequence_no,
                tool_name=trace.tool_name,
                input_summary=trace.input_summary,
                ok=trace.ok,
                elapsed_ms=trace.elapsed_ms,
                error=trace.error,
                created_at=_now(),
            ))
        trace.sequence_no = sequence_no
        return trace

    def list_trace(self, session_id: str) -> list[ToolTraceEntry]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(tool_traces).where(tool_traces.c.session_id == session_id).order_by(tool_traces.c.sequence_no)).mappings().all()
        return [
            ToolTraceEntry(tool_name=row["tool_name"], input_summary=row["input_summary"], ok=row["ok"], elapsed_ms=row["elapsed_ms"], error=row["error"], sequence_no=row["sequence_no"])
            for row in rows
        ]
