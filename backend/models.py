from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    market_code: Mapped[str] = mapped_column(String(4), unique=True, nullable=False)
    market_name: Mapped[str] = mapped_column(String(80), nullable=False)
    expert_name: Mapped[str] = mapped_column(String(120), nullable=False)
    expert_role: Mapped[str] = mapped_column(String(160), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_incomplete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingestion_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    turns: Mapped[list["TranscriptTurn"]] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptTurn.turn_order",
    )


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transcript_id: Mapped[str] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_id: Mapped[str | None] = mapped_column(
        String(16), unique=True, index=True, nullable=True
    )
    timestamp: Mapped[str] = mapped_column(String(8), nullable=False)
    speaker: Mapped[str] = mapped_column(String(120), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    preceding_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_expert_answer: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, nullable=False
    )

    transcript: Mapped[Transcript] = relationship(back_populates="turns")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_corpus_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    files_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    turns_indexed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vector_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
class GeneratedAnalysis(Base):
    __tablename__ = "generated_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    analysis_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    output_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )