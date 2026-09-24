from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.citation_service import get_citation, validate_citation_ids
from backend.database import Base
from backend.models import Transcript, TranscriptTurn


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    transcript = Transcript(
        id="FR",
        filename="Transcript_1_France.txt",
        market_code="FR",
        market_name="France",
        expert_name="Dr. Jean Martin",
        expert_role="Head of Urology",
        raw_text="source",
        is_incomplete=False,
        ingestion_hash="hash",
    )
    turn = TranscriptTurn(
        transcript_id="FR",
        chunk_id="FR-06:08",
        timestamp="06:08",
        speaker="Dr. Martin",
        text="Six to twelve months is realistic once the hospital becomes serious.",
        preceding_question="How long does a purchase decision normally take?",
        turn_order=1,
        is_expert_answer=True,
    )
    session.add_all([transcript, turn])
    session.commit()
    return session


def test_accepts_valid_retrieved_citation():
    session = build_session()
    valid, invalid = validate_citation_ids(
        ["FR-06:08"],
        {"FR-06:08"},
        session,
    )

    assert valid is True
    assert invalid == []


def test_rejects_citation_absent_from_retrieved_evidence():
    session = build_session()
    valid, invalid = validate_citation_ids(
        ["DE-04:09"],
        {"FR-06:08"},
        session,
    )

    assert valid is False
    assert invalid == ["DE-04:09"]


def test_quote_is_retrieved_from_stored_source():
    session = build_session()
    citation = get_citation(session, "FR-06:08")

    generated_text = "The model invented a different quote."
    assert citation is not None
    assert citation.quote != generated_text
    assert citation.quote == (
        "Six to twelve months is realistic once the hospital becomes serious."
    )