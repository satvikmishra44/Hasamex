from contextlib import asynccontextmanager

import chromadb
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.analysis_service import answer_question, get_guide, get_insights
from backend.citation_service import get_citation
from backend.config import settings
from backend.database import get_db, init_db
from backend.ingestion import run_ingestion, collect_raw_file_checks
from backend.models import IngestionRun, Transcript, TranscriptTurn
from backend.schemas import (
    AnswerResponse,
    ChatRequest,
    Citation,
    IngestionResponse,
    SystemStatus,
    TranscriptDetail,
    TranscriptSummary,
    TurnResponse,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    try:
        run_ingestion(force=False)
    except Exception:
        pass
    yield


app = FastAPI(
    title="Expert Call Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=settings.static_path), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(settings.static_path / "index.html")


@app.get("/api/health")
def health(session: Session = Depends(get_db)):
    transcript_count = session.scalar(select(func.count(Transcript.id))) or 0
    return {
        "status": "ok",
        "service": "Expert Call Intelligence",
        "database": "ready",
        "transcripts": transcript_count,
    }


@app.get("/api/transcripts", response_model=list[TranscriptSummary])
def transcripts(session: Session = Depends(get_db)):
    rows = session.scalars(
        select(Transcript).order_by(Transcript.market_code)
    ).all()
    return [
        TranscriptSummary(
            id=item.id,
            filename=item.filename,
            market_code=item.market_code,
            market_name=item.market_name,
            expert_name=item.expert_name,
            expert_role=item.expert_role,
            is_incomplete=item.is_incomplete,
            expert_turn_count=sum(turn.is_expert_answer for turn in item.turns),
        )
        for item in rows
    ]


@app.get("/api/transcripts/{transcript_id}", response_model=TranscriptDetail)
def transcript_detail(transcript_id: str, session: Session = Depends(get_db)):
    transcript = session.get(Transcript, transcript_id.upper())
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found.")

    return TranscriptDetail(
        id=transcript.id,
        filename=transcript.filename,
        market_code=transcript.market_code,
        market_name=transcript.market_name,
        expert_name=transcript.expert_name,
        expert_role=transcript.expert_role,
        is_incomplete=transcript.is_incomplete,
        expert_turn_count=sum(turn.is_expert_answer for turn in transcript.turns),
        turns=[
            TurnResponse(
                timestamp=turn.timestamp,
                speaker=turn.speaker,
                text=turn.text,
                chunk_id=turn.chunk_id,
                preceding_question=turn.preceding_question,
                turn_order=turn.turn_order,
                is_expert_answer=turn.is_expert_answer,
            )
            for turn in transcript.turns
        ],
    )


@app.get("/api/evidence/{chunk_id}", response_model=Citation)
def evidence(chunk_id: str, session: Session = Depends(get_db)):
    citation = get_citation(session, chunk_id.upper())
    if not citation:
        raise HTTPException(status_code=404, detail="Evidence chunk not found.")
    return citation


@app.get("/api/guide")
def guide(session: Session = Depends(get_db)):
    return get_guide(session)


@app.get("/api/insights")
def insights(session: Session = Depends(get_db)):
    return get_insights(session)


@app.get("/api/overview")
def overview(session: Session = Depends(get_db)):
    transcript_rows = session.scalars(
        select(Transcript).order_by(Transcript.market_name)
    ).all()

    calls = len(transcript_rows)
    moments = session.scalar(
        select(func.count(TranscriptTurn.id)).where(
            TranscriptTurn.is_expert_answer.is_(True)
        )
    ) or 0
    incomplete = session.scalar(
        select(func.count(Transcript.id)).where(Transcript.is_incomplete.is_(True))
    ) or 0

    guide_data = get_guide(session)

    question_map = {}
    for item in guide_data["questions"]:
        question_map[item["number"]] = item

    def summary_for_market(market_name: str, question_number: int) -> str:
        question = question_map.get(question_number)
        if not question:
            return "No evidence available."
        for answer in question["answers"]:
            if answer["market"] == market_name:
                return answer["summary"]
        return "No evidence available."

    markets_summary = [
        {
            "market": row.market_name,
            "adoption": summary_for_market(row.market_name, 1),
            "focus": summary_for_market(row.market_name, 3),
            "timeline": summary_for_market(row.market_name, 6),
        }
        for row in transcript_rows
    ]

    return {
        "calls": calls,
        "markets": [item.market_name for item in transcript_rows],
        "expert_moments": moments,
        "incomplete_transcripts": incomplete,
        "source_integrity": "Timestamp-preserved source text",
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.gemini_model,
        "snapshots": [
            {
                "title": "Adoption",
                "text": "Guide answers are derived automatically from the current transcript corpus.",
            },
            {
                "title": "Purchase drivers",
                "text": "Economics, budgets, utilization, training, and clinical strategy are extracted from retrieved evidence.",
            },
            {
                "title": "Training",
                "text": "Training-related findings update automatically whenever new expert calls are ingested.",
            },
            {
                "title": "Evidence gaps",
                "text": "Missing answers remain missing. The application does not invent unsupported details.",
            },
        ],
        "markets_summary": markets_summary,
    }

@app.post("/api/chat/all", response_model=AnswerResponse)
def chat_all(request: ChatRequest, session: Session = Depends(get_db)):
    return answer_question(
        session=session,
        question=request.question,
        api_key=request.api_key.get_secret_value() if request.api_key else None,
        model=request.model,
    )


@app.post(
    "/api/chat/transcript/{transcript_id}",
    response_model=AnswerResponse,
)
def chat_transcript(
    transcript_id: str,
    request: ChatRequest,
    session: Session = Depends(get_db),
):
    transcript_id = transcript_id.upper()
    if not session.get(Transcript, transcript_id):
        raise HTTPException(status_code=404, detail="Transcript not found.")

    return answer_question(
        session=session,
        question=request.question,
        transcript_id=transcript_id,
        api_key=request.api_key.get_secret_value() if request.api_key else None,
        model=request.model,
    )


@app.get("/api/system/status", response_model=SystemStatus)
def system_status(session: Session = Depends(get_db)):
    calls = session.scalar(select(func.count(Transcript.id))) or 0
    chunks = session.scalar(
        select(func.count(TranscriptTurn.id)).where(
            TranscriptTurn.is_expert_answer.is_(True)
        )
    ) or 0
    incomplete = session.scalar(
        select(func.count(Transcript.id)).where(Transcript.is_incomplete.is_(True))
    ) or 0

    last_completed_run = session.scalar(
        select(IngestionRun)
        .where(IngestionRun.status == "completed")
        .order_by(IngestionRun.completed_at.desc())
        .limit(1)
    )
    latest_run = session.scalar(
        select(IngestionRun)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )

    raw_file_checks, valid_files = collect_raw_file_checks()

    chroma_status = "Not initialized"
    try:
        client = chromadb.PersistentClient(path=str(settings.chroma_path))
        collection = client.get_collection(
            name="expert_call_answers",
            embedding_function=None,
        )
        chroma_status = f"Ready · {collection.count()} records"
    except Exception:
        pass

    return SystemStatus(
        raw_files_detected=len(raw_file_checks),
        valid_raw_files=len(valid_files),
        invalid_raw_files=len(raw_file_checks) - len(valid_files),
        calls_parsed=calls,
        expert_chunks_indexed=chunks,
        sqlite_path=str(settings.database_path),
        sqlite_status="Ready" if settings.database_path.exists() else "Not initialized",
        chroma_path=str(settings.chroma_path),
        chroma_status=chroma_status,
        embedding_model=settings.embedding_model,
        gemini_configured=bool(settings.gemini_api_key),
        gemini_model=settings.gemini_model,
        last_ingestion_time=(
            last_completed_run.completed_at.isoformat()
            if last_completed_run and last_completed_run.completed_at
            else None
        ),
        incomplete_transcripts=incomplete,
        raw_corpus_fingerprint=(
            last_completed_run.raw_corpus_fingerprint
            if last_completed_run else None
        ),
        last_ingestion_skipped=bool(
            latest_run and latest_run.message == "Raw corpus unchanged. Ingestion skipped."
        ),
        raw_file_checks=raw_file_checks,
    )

@app.post("/api/ingest", response_model=IngestionResponse)
def ingest():
    try:
        return run_ingestion()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc