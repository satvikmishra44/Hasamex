from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

from backend.config import settings

Coverage = Literal["sufficient", "partial", "insufficient"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=settings.max_query_length)
    api_key: SecretStr | None = None
    model: str | None = Field(default=None, max_length=120)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank.")
        return value

    @field_validator("model")
    @classmethod
    def clean_model(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class GeneratedClaim(BaseModel):
    claim: str
    citation_ids: list[str]


class GeminiPayload(BaseModel):
    answer: str
    claims: list[GeneratedClaim]
    coverage: Coverage
    limitations: list[str] = []


class Citation(BaseModel):
    chunk_id: str
    transcript_id: str
    transcript_name: str
    market: str
    market_code: str
    expert_name: str
    expert_role: str
    timestamp: str
    quote: str
    preceding_question: str | None
    incomplete_transcript: bool
    relevance_score: float | None = None


class AnswerResponse(BaseModel):
    answer: str
    claims: list[GeneratedClaim]
    coverage: Coverage
    limitations: list[str]
    evidence: list[Citation]
    retrieval_summary: str
    generation_mode: str


class TurnResponse(BaseModel):
    timestamp: str
    speaker: str
    text: str
    chunk_id: str | None
    preceding_question: str | None
    turn_order: int
    is_expert_answer: bool


class TranscriptSummary(BaseModel):
    id: str
    filename: str
    market_code: str
    market_name: str
    expert_name: str
    expert_role: str
    is_incomplete: bool
    expert_turn_count: int


class TranscriptDetail(TranscriptSummary):
    turns: list[TurnResponse]


class IngestionResponse(BaseModel):
    status: str
    files_read: int
    transcripts_created: int
    transcripts_updated: int
    expert_turns_indexed: int
    vector_records_created: int
    vector_records_synchronized: int
    incomplete_transcripts: int
    message: str


class SystemStatus(BaseModel):
    raw_files_detected: int
    calls_parsed: int
    expert_chunks_indexed: int
    sqlite_path: str
    sqlite_status: str
    chroma_path: str
    chroma_status: str
    embedding_model: str
    gemini_configured: bool
    gemini_model: str
    last_ingestion_time: str | None
    incomplete_transcripts: int