import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Transcript, TranscriptTurn
from backend.schemas import Citation, GeminiPayload
from backend.retrieval import RetrievalRecord

CITATION_PATTERN = re.compile(r"\b(?:FR|DE|UK)-\d{2}:\d{2}\b")


def validate_citation_ids(
    citation_ids: list[str],
    retrieved_ids: set[str],
    session: Session,
) -> tuple[bool, list[str]]:
    invalid = sorted(set(citation_ids) - retrieved_ids)
    if invalid:
        return False, invalid

    if citation_ids:
        stored = set(
            session.scalars(
                select(TranscriptTurn.chunk_id).where(
                    TranscriptTurn.chunk_id.in_(citation_ids),
                    TranscriptTurn.is_expert_answer.is_(True),
                )
            ).all()
        )
        invalid.extend(sorted(set(citation_ids) - stored))

    return not invalid, sorted(set(invalid))


def validate_generated_payload(
    payload: GeminiPayload,
    retrieved_ids: set[str],
    session: Session,
) -> tuple[bool, list[str]]:
    cited = [
        citation_id
        for claim in payload.claims
        for citation_id in claim.citation_ids
    ]
    cited.extend(CITATION_PATTERN.findall(payload.answer))

    if payload.coverage != "insufficient":
        if not payload.claims or any(not claim.citation_ids for claim in payload.claims):
            return False, ["Each supported claim requires a citation."]

    return validate_citation_ids(cited, retrieved_ids, session)


def citation_from_record(record: RetrievalRecord) -> Citation:
    return Citation(
        chunk_id=record.chunk_id,
        transcript_id=record.transcript_id,
        transcript_name=record.transcript_name,
        market=record.market,
        market_code=record.market_code,
        expert_name=record.expert_name,
        expert_role=record.expert_role,
        timestamp=record.timestamp,
        quote=record.source_text,
        preceding_question=record.preceding_question,
        incomplete_transcript=record.incomplete_transcript,
        relevance_score=record.relevance_score,
    )


def get_citation(session: Session, chunk_id: str) -> Citation | None:
    row = session.execute(
        select(TranscriptTurn, Transcript)
        .join(Transcript, Transcript.id == TranscriptTurn.transcript_id)
        .where(
            TranscriptTurn.chunk_id == chunk_id,
            TranscriptTurn.is_expert_answer.is_(True),
        )
    ).first()

    if not row:
        return None

    turn, transcript = row
    return Citation(
        chunk_id=turn.chunk_id,
        transcript_id=transcript.id,
        transcript_name=transcript.filename,
        market=transcript.market_name,
        market_code=transcript.market_code,
        expert_name=transcript.expert_name,
        expert_role=transcript.expert_role,
        timestamp=turn.timestamp,
        quote=turn.text,
        preceding_question=turn.preceding_question,
        incomplete_transcript=transcript.is_incomplete,
        relevance_score=None,
    )


def get_citations(session: Session, chunk_ids: list[str]) -> list[Citation]:
    citations: list[Citation] = []
    for chunk_id in chunk_ids:
        citation = get_citation(session, chunk_id)
        if citation:
            citations.append(citation)
    return citations