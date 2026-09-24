from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.gemini_service import INSUFFICIENT_MESSAGE, deterministic_response
from backend.models import Transcript, TranscriptTurn
from backend.parser import parse_transcript
from backend.retrieval import HybridRetriever

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    for filename in (
        "Transcript_1_France.txt",
        "Transcript_2_Germany.txt",
        "Transcript_3_UK.txt",
    ):
        parsed = parse_transcript(RAW / filename)
        session.add(
            Transcript(
                id=parsed.transcript_id,
                filename=parsed.filename,
                market_code=parsed.market_code,
                market_name=parsed.market_name,
                expert_name=parsed.expert_name,
                expert_role=parsed.expert_role,
                raw_text=parsed.raw_text,
                is_incomplete=parsed.is_incomplete,
                ingestion_hash="test",
            )
        )
        session.flush()

        for turn in parsed.turns:
            session.add(
                TranscriptTurn(
                    transcript_id=parsed.transcript_id,
                    chunk_id=turn.chunk_id,
                    timestamp=turn.timestamp,
                    speaker=turn.speaker,
                    text=turn.text,
                    preceding_question=turn.preceding_question,
                    turn_order=turn.turn_order,
                    is_expert_answer=turn.is_expert_answer,
                )
            )

    session.commit()
    return session


def test_retrieval_returns_france_timeline_chunk():
    session = build_session()
    results = HybridRetriever(session, enable_semantic=False).retrieve(
        "How long does procurement take?",
        limit=5,
    )

    assert results
    assert results[0].chunk_id == "FR-06:08"


def test_per_transcript_retrieval_respects_scope():
    session = build_session()
    results = HybridRetriever(session, enable_semantic=False).retrieve(
        "What are the main barriers and costs?",
        transcript_id="DE",
        limit=5,
    )

    assert results
    assert all(item.transcript_id == "DE" for item in results)
    assert any(item.chunk_id == "DE-01:10" for item in results)


def test_unsupported_question_returns_insufficient_state():
    session = build_session()
    results = HybridRetriever(session, enable_semantic=False).retrieve(
        "Which company has the biggest market share?",
        limit=5,
    )
    response = deterministic_response(results)

    assert results == []
    assert response.coverage == "insufficient"
    assert response.answer == INSUFFICIENT_MESSAGE