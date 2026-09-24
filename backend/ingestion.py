import hashlib
from datetime import datetime, timezone

import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy import select

from backend.config import settings
from backend.database import SessionLocal, init_db
from backend.models import IngestionRun, Transcript, TranscriptTurn
from backend.parser import ParsedTranscript, parse_transcript

TRANSCRIPT_FILES = (
    "Transcript_1_France.txt",
    "Transcript_2_Germany.txt",
    "Transcript_3_UK.txt",
)

_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_sources() -> list[ParsedTranscript]:
    parsed: list[ParsedTranscript] = []
    for filename in TRANSCRIPT_FILES:
        path = settings.raw_path / filename
        if not path.exists():
            raise FileNotFoundError(f"Required source file is missing: {path}")
        parsed.append(parse_transcript(path))
    return parsed


def vector_metadata(parsed: ParsedTranscript, turn) -> dict:
    return {
        "chunk_id": turn.chunk_id,
        "transcript_id": parsed.transcript_id,
        "transcript_name": parsed.filename,
        "market": parsed.market_name,
        "market_code": parsed.market_code,
        "expert_name": parsed.expert_name,
        "expert_role": parsed.expert_role,
        "timestamp": turn.timestamp,
        "preceding_question": turn.preceding_question or "",
        "incomplete_transcript": parsed.is_incomplete,
        "source_text": turn.text,
    }


def synchronize_vectors(parsed_sources: list[ParsedTranscript]) -> tuple[int, int]:
    records = [
        (parsed, turn)
        for parsed in parsed_sources
        for turn in parsed.turns
        if turn.is_expert_answer and turn.chunk_id
    ]

    client = chromadb.PersistentClient(path=str(settings.chroma_path))
    collection = client.get_or_create_collection(
        name="expert_call_answers",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )

    existing = set(collection.get()["ids"])
    expected = {turn.chunk_id for _, turn in records if turn.chunk_id}
    stale = sorted(existing - expected)

    if stale:
        collection.delete(ids=stale)

    documents = [
        f"{turn.preceding_question or ''}\n{turn.text}".strip()
        for _, turn in records
    ]
    embeddings = get_embedding_model().encode(
        documents,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    ids = [turn.chunk_id for _, turn in records]
    metadatas = [vector_metadata(parsed, turn) for parsed, turn in records]

    if ids:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    return len(expected - existing), len(ids)


def run_ingestion() -> dict:
    init_db()
    started = datetime.now(timezone.utc)
    session = SessionLocal()
    run = IngestionRun(
        started_at=started,
        status="running",
        message="Ingestion started.",
    )
    session.add(run)
    session.commit()

    try:
        parsed_sources = parse_sources()
        created = 0
        updated = 0
        expert_turns = 0

        for parsed in parsed_sources:
            digest = source_hash(parsed.raw_text)
            transcript = session.get(Transcript, parsed.transcript_id)

            if transcript is None:
                transcript = Transcript(
                    id=parsed.transcript_id,
                    filename=parsed.filename,
                    market_code=parsed.market_code,
                    market_name=parsed.market_name,
                    expert_name=parsed.expert_name,
                    expert_role=parsed.expert_role,
                    raw_text=parsed.raw_text,
                    is_incomplete=parsed.is_incomplete,
                    ingestion_hash=digest,
                    ingested_at=started,
                )
                session.add(transcript)
                session.flush()
                created += 1
            elif transcript.ingestion_hash != digest:
                transcript.filename = parsed.filename
                transcript.market_name = parsed.market_name
                transcript.expert_name = parsed.expert_name
                transcript.expert_role = parsed.expert_role
                transcript.raw_text = parsed.raw_text
                transcript.is_incomplete = parsed.is_incomplete
                transcript.ingestion_hash = digest
                transcript.ingested_at = started
                updated += 1
            else:
                existing_count = session.scalar(
                    select(TranscriptTurn)
                    .where(TranscriptTurn.transcript_id == parsed.transcript_id)
                    .limit(1)
                )
                if existing_count is not None:
                    expert_turns += sum(t.is_expert_answer for t in parsed.turns)
                    continue

            session.query(TranscriptTurn).filter(
                TranscriptTurn.transcript_id == parsed.transcript_id
            ).delete(synchronize_session=False)

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
                expert_turns += int(turn.is_expert_answer)

        session.commit()
        vectors_created, vectors_synchronized = synchronize_vectors(parsed_sources)
        incomplete_count = sum(item.is_incomplete for item in parsed_sources)

        result = {
            "status": "completed",
            "files_read": len(parsed_sources),
            "transcripts_created": created,
            "transcripts_updated": updated,
            "expert_turns_indexed": expert_turns,
            "vector_records_created": vectors_created,
            "vector_records_synchronized": vectors_synchronized,
            "incomplete_transcripts": incomplete_count,
            "message": (
                f"Processed {len(parsed_sources)} files and synchronized "
                f"{vectors_synchronized} expert-answer vectors."
            ),
        }

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.files_processed = len(parsed_sources)
        run.turns_indexed = expert_turns
        run.vector_records = vectors_synchronized
        run.message = result["message"]
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        failed_run = session.get(IngestionRun, run.id)
        if failed_run:
            failed_run.status = "failed"
            failed_run.completed_at = datetime.now(timezone.utc)
            failed_run.message = str(exc)
            session.commit()
        raise
    finally:
        session.close()