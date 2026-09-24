import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

import chromadb
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.ingestion import get_embedding_model
from backend.models import Transcript, TranscriptTurn

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "of", "on", "or", "the", "their",
    "this", "to", "was", "were", "what", "which", "who", "why", "with",
    "robotic", "surgery", "market", "europe", "european",
}
EXPANSIONS = {
    "procurement": {"purchase", "purchasing", "decision", "approval", "timeline"},
    "timeline": {"long", "months", "purchase", "decision", "cycle"},
    "long": {"months", "timeline", "decision", "purchase"},
    "roi": {"economic", "economics", "finance", "utilisation", "utilization", "volume"},
    "training": {"surgeon", "staff", "comfortable", "utilisation", "utilization"},
    "adoption": {"growing", "increasing", "growth", "advanced", "access"},
    "barriers": {"barrier", "cost", "funding", "budget", "training", "approval"},
    "maintenance": {"maintenance", "service", "contracts", "cost"},
    "outlook": {"growth", "gradual", "accelerate", "years", "expect"},
}
UNSUPPORTED_PATTERNS = (
    "market share",
    "biggest company",
    "largest company",
    "robot price",
    "robot prices",
    "system price",
    "system prices",
    "cagr",
    "market size",
    "revenue forecast",
)


@dataclass
class RetrievalRecord:
    chunk_id: str
    transcript_id: str
    transcript_name: str
    market: str
    market_code: str
    expert_name: str
    expert_role: str
    timestamp: str
    source_text: str
    preceding_question: str | None
    incomplete_transcript: bool
    relevance_score: float = 0.0


def tokenize(text: str, expand: bool = False) -> list[str]:
    tokens = [
        token for token in TOKEN_RE.findall(text.lower())
        if token not in STOP_WORDS and len(token) > 1
    ]
    if expand:
        expanded = list(tokens)
        for token in tokens:
            expanded.extend(EXPANSIONS.get(token, set()))
        return expanded
    return tokens


def lexical_scores(query: str, records: list[RetrievalRecord]) -> dict[str, float]:
    query_terms = tokenize(query, expand=True)
    if not query_terms or not records:
        return {record.chunk_id: 0.0 for record in records}

    documents = [
        tokenize(
            " ".join(
                [
                    record.source_text,
                    record.preceding_question or "",
                    record.expert_name,
                    record.market,
                ]
            )
        )
        for record in records
    ]
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    average_length = sum(len(document) for document in documents) / max(len(documents), 1)
    scores: dict[str, float] = {}

    for record, document in zip(records, documents):
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if frequency == 0:
                continue
            idf = math.log(
                1 + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.5 * (
                0.25 + 0.75 * len(document) / max(average_length, 1)
            )
            score += idf * (frequency * 2.5) / denominator
        scores[record.chunk_id] = score

    return scores


def query_is_explicitly_unsupported(query: str) -> bool:
    lowered = query.lower()
    return any(pattern in lowered for pattern in UNSUPPORTED_PATTERNS)


class HybridRetriever:
    def __init__(self, session: Session, enable_semantic: bool = True):
        self.session = session
        self.enable_semantic = enable_semantic

    def _records(self, transcript_id: str | None = None) -> list[RetrievalRecord]:
        statement = (
            select(TranscriptTurn, Transcript)
            .join(Transcript, Transcript.id == TranscriptTurn.transcript_id)
            .where(TranscriptTurn.is_expert_answer.is_(True))
        )
        if transcript_id:
            statement = statement.where(
                TranscriptTurn.transcript_id == transcript_id.upper()
            )

        rows = self.session.execute(statement).all()
        return [
            RetrievalRecord(
                chunk_id=turn.chunk_id,
                transcript_id=transcript.id,
                transcript_name=transcript.filename,
                market=transcript.market_name,
                market_code=transcript.market_code,
                expert_name=transcript.expert_name,
                expert_role=transcript.expert_role,
                timestamp=turn.timestamp,
                source_text=turn.text,
                preceding_question=turn.preceding_question,
                incomplete_transcript=transcript.is_incomplete,
            )
            for turn, transcript in rows
            if turn.chunk_id
        ]

    def _semantic_scores(
        self, query: str, transcript_id: str | None, available: int
    ) -> dict[str, float]:
        if not self.enable_semantic or available == 0:
            return {}

        try:
            client = chromadb.PersistentClient(path=str(settings.chroma_path))
            collection = client.get_collection(
                name="expert_call_answers",
                embedding_function=None,
            )
            if collection.count() == 0:
                return {}

            query_embedding = get_embedding_model().encode(
                [query],
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist()

            kwargs = {
                "query_embeddings": query_embedding,
                "n_results": min(max(available, 1), 24),
                "include": ["distances"],
            }
            if transcript_id:
                kwargs["where"] = {"transcript_id": transcript_id.upper()}

            result = collection.query(**kwargs)
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]
            return {
                chunk_id: max(0.0, min(1.0, 1.0 - float(distance) / 2.0))
                for chunk_id, distance in zip(ids, distances)
            }
        except Exception:
            return {}

    @staticmethod
    def _diverse(records: list[RetrievalRecord], limit: int) -> list[RetrievalRecord]:
        buckets: dict[str, list[RetrievalRecord]] = defaultdict(list)
        for record in records:
            buckets[record.transcript_id].append(record)

        active = sorted(
            buckets,
            key=lambda key: buckets[key][0].relevance_score,
            reverse=True,
        )
        selected: list[RetrievalRecord] = []

        while active and len(selected) < limit:
            next_active: list[str] = []
            for transcript_id in active:
                if buckets[transcript_id] and len(selected) < limit:
                    selected.append(buckets[transcript_id].pop(0))
                if buckets[transcript_id]:
                    next_active.append(transcript_id)
            active = next_active

        return selected

    def retrieve(
        self,
        query: str,
        transcript_id: str | None = None,
        limit: int = 8,
    ) -> list[RetrievalRecord]:
        if query_is_explicitly_unsupported(query):
            return []

        records = self._records(transcript_id)
        if not records:
            return []

        lexical = lexical_scores(query, records)
        semantic = self._semantic_scores(query, transcript_id, len(records))
        max_lexical = max(lexical.values(), default=0.0)

        ranked: list[RetrievalRecord] = []
        for record in records:
            normalized_lexical = (
                lexical[record.chunk_id] / max_lexical if max_lexical > 0 else 0.0
            )
            semantic_score = semantic.get(record.chunk_id, 0.0)
            record.relevance_score = round(
                0.58 * semantic_score + 0.42 * normalized_lexical,
                4,
            )
            if lexical[record.chunk_id] > 0 or semantic_score >= 0.46:
                ranked.append(record)

        ranked.sort(key=lambda item: item.relevance_score, reverse=True)
        if not ranked or ranked[0].relevance_score < 0.18:
            return []

        return self._diverse(ranked, min(limit, 8))


def retrieval_summary(records: list[RetrievalRecord], grounded: bool = False) -> str:
    calls = len({record.transcript_id for record in records})
    prefix = "Grounded in" if grounded else "Retrieved"
    noun = "call" if calls == 1 else "calls"
    return f"{prefix} {len(records)} evidence moments across {calls} {noun}."