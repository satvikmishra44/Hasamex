import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy import select

from backend.analysis_service import refresh_derived_analysis
from backend.config import settings
from backend.database import SessionLocal, init_db
from backend.models import IngestionRun, Transcript, TranscriptTurn
from backend.parser import ParsedTranscript, parse_transcript, validate_transcript_format

_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover_transcript_files() -> list[Path]:
    return sorted(
        path
        for path in settings.raw_path.glob("*.txt")
        if path.name != "Interview_Guide.txt"
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_raw_corpus_fingerprint(valid_files: list[tuple[Path, str]]) -> str:
    payload = [
        {"filename": path.name, "hash": digest}
        for path, digest in sorted(valid_files, key=lambda item: item[0].name.lower())
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def get_last_successful_fingerprint(session) -> str | None:
    return session.scalar(
        select(IngestionRun.raw_corpus_fingerprint)
        .where(IngestionRun.status == "completed")
        .order_by(IngestionRun.completed_at.desc())
        .limit(1)
    )


def collect_raw_file_checks():
    checks = []
    valid_files = []

    for path in discover_transcript_files():
        validation = validate_transcript_format(path)
        checks.append(
            {
                "filename": path.name,
                "valid": validation.valid,
                "reason": validation.reason,
                "market_name": validation.market_name,
                "market_code": validation.market_code,
                "expert_name": validation.expert_name,
            }
        )
        if validation.valid:
            valid_files.append((path, file_hash(path)))

    return checks, valid_files


def parse_valid_sources(valid_files: list[tuple[Path, str]]) -> list[ParsedTranscript]:
    parsed: list[ParsedTranscript] = []
    for path, _digest in valid_files:
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

    existing = set(collection.get().get("ids", []))
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


def run_ingestion(force: bool = False) -> dict:
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
        raw_file_checks, valid_files = collect_raw_file_checks()
        fingerprint = build_raw_corpus_fingerprint(valid_files) if valid_files else None
        last_fingerprint = get_last_successful_fingerprint(session)

        run.files_discovered = len(raw_file_checks)
        run.valid_files = len(valid_files)
        run.invalid_files = len(raw_file_checks) - len(valid_files)
        run.raw_corpus_fingerprint = fingerprint

        if not force and fingerprint and fingerprint == last_fingerprint:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.files_processed = 0
            run.turns_indexed = 0
            run.vector_records = 0
            run.message = "Raw corpus unchanged. Ingestion skipped."
            session.commit()

            return {
                "status": "completed",
                "files_discovered": len(raw_file_checks),
                "valid_files": len(valid_files),
                "invalid_files": len(raw_file_checks) - len(valid_files),
                "files_read": 0,
                "transcripts_created": 0,
                "transcripts_updated": 0,
                "expert_turns_indexed": 0,
                "vector_records_created": 0,
                "vector_records_synchronized": 0,
                "incomplete_transcripts": session.query(Transcript).filter(
                    Transcript.is_incomplete.is_(True)
                ).count(),
                "raw_corpus_fingerprint": fingerprint,
                "skipped": True,
                "raw_file_checks": raw_file_checks,
                "message": "Raw corpus unchanged. Ingestion skipped.",
            }

        parsed_sources = parse_valid_sources(valid_files)
        expected_ids = {parsed.transcript_id for parsed in parsed_sources}
        existing_ids = set(session.scalars(select(Transcript.id)).all())
        stale_ids = existing_ids - expected_ids

        if stale_ids:
            session.query(TranscriptTurn).filter(
                TranscriptTurn.transcript_id.in_(stale_ids)
            ).delete(synchronize_session=False)
            session.query(Transcript).filter(
                Transcript.id.in_(stale_ids)
            ).delete(synchronize_session=False)

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
                existing_turn = session.scalar(
                    select(TranscriptTurn.id)
                    .where(TranscriptTurn.transcript_id == parsed.transcript_id)
                    .limit(1)
                )
                if existing_turn is not None:
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
        refresh_derived_analysis(session)
        session.commit()

        incomplete_count = sum(item.is_incomplete for item in parsed_sources)

        result = {
            "status": "completed",
            "files_discovered": len(raw_file_checks),
            "valid_files": len(valid_files),
            "invalid_files": len(raw_file_checks) - len(valid_files),
            "files_read": len(parsed_sources),
            "transcripts_created": created,
            "transcripts_updated": updated,
            "expert_turns_indexed": expert_turns,
            "vector_records_created": vectors_created,
            "vector_records_synchronized": vectors_synchronized,
            "incomplete_transcripts": incomplete_count,
            "raw_corpus_fingerprint": fingerprint,
            "skipped": False,
            "raw_file_checks": raw_file_checks,
            "message": (
                f"Processed {len(parsed_sources)} valid transcript files and "
                f"synchronized {vectors_synchronized} expert-answer vectors."
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