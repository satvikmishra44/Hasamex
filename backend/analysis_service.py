import hashlib
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.citation_service import citation_from_record
from backend.gemini_service import generate_grounded_answer
from backend.models import GeneratedAnalysis, Transcript
from backend.retrieval import HybridRetriever

GUIDE_QUESTIONS = [
    "How would you describe current adoption of robotic surgery in your market?",
    "What are the main barriers to adoption?",
    "How important are hospital budgets and ROI in purchasing decisions?",
    "How important are surgeon training and clinical outcomes?",
    "What adoption trend do you expect over the next 3–5 years?",
    "What is the typical hospital decision-making timeline for purchasing a new robotic system?",
]


def current_evidence_fingerprint(session: Session) -> str:
    rows = session.execute(
        select(Transcript.id, Transcript.ingestion_hash).order_by(Transcript.id)
    ).all()
    payload = [{"id": row[0], "hash": row[1]} for row in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def market_rows(session: Session):
    return session.scalars(select(Transcript).order_by(Transcript.market_name)).all()


def build_guide_analysis(session: Session) -> dict:
    retriever = HybridRetriever(session)
    markets = market_rows(session)
    questions = []

    for index, question in enumerate(GUIDE_QUESTIONS, start=1):
        answers = []
        for transcript in markets:
            evidence = retriever.retrieve(question, transcript_id=transcript.id, limit=4)
            if not evidence:
                answers.append(
                    {
                        "market_code": transcript.market_code,
                        "market": transcript.market_name,
                        "summary": f"No evidence for this question in the supplied {transcript.market_name} call.",
                        "coverage": "insufficient",
                        "citations": [],
                    }
                )
                continue

            coverage = (
                "partial"
                if any(item.incomplete_transcript for item in evidence)
                else "sufficient"
            )
            summary = evidence[0].source_text
            answers.append(
                {
                    "market_code": transcript.market_code,
                    "market": transcript.market_name,
                    "summary": summary,
                    "coverage": coverage,
                    "citations": [
                        citation_from_record(item).model_dump() for item in evidence
                    ],
                }
            )

        questions.append(
            {
                "number": index,
                "question": question,
                "answers": answers,
            }
        )

    return {"questions": questions}


def build_insights_analysis(session: Session) -> dict:
    theme_queries = [
        ("Adoption", "How would you describe current adoption of robotic surgery in your market?"),
        ("Barriers", "What are the main barriers to adoption?"),
        ("Economics", "How important are hospital budgets and ROI in purchasing decisions?"),
        ("Training", "How important are surgeon training and clinical outcomes?"),
        ("Outlook", "What adoption trend do you expect over the next 3–5 years?"),
        ("Timeline", "What is the typical hospital decision-making timeline for purchasing a new robotic system?"),
    ]

    retriever = HybridRetriever(session)
    shared_themes = []
    differences = []

    for label, query in theme_queries:
        evidence = retriever.retrieve(query, limit=8)
        if len(evidence) < 2:
            continue

        markets = sorted({item.market for item in evidence})
        shared_themes.append(
            {
                "category": "Shared theme",
                "title": label,
                "explanation": f"Automatically derived evidence cluster for {label.lower()} across the available calls.",
                "countries": markets,
                "citations": [
                    citation_from_record(item).model_dump() for item in evidence[:4]
                ],
            }
        )

        by_market = defaultdict(list)
        for item in evidence:
            by_market[item.market].append(item)

        if len(by_market) >= 2:
            differences.append(
                {
                    "category": "Difference in emphasis",
                    "title": f"{label} emphasis varies by market",
                    "explanation": f"Different calls emphasize different aspects of {label.lower()} based on their retrieved evidence.",
                    "countries": sorted(by_market.keys()),
                    "citations": [
                        citation_from_record(items[0]).model_dump()
                        for items in by_market.values()
                    ],
                }
            )

    return {
        "shared_themes": shared_themes,
        "differences": differences,
    }


def upsert_generated_analysis(
    session: Session,
    analysis_type: str,
    analysis_key: str,
    output: dict,
    fingerprint: str,
) -> None:
    existing = session.scalar(
        select(GeneratedAnalysis).where(
            GeneratedAnalysis.analysis_type == analysis_type,
            GeneratedAnalysis.analysis_key == analysis_key,
        )
    )

    serialized = json.dumps(output)
    if existing:
        existing.output_json = serialized
        existing.evidence_fingerprint = fingerprint
    else:
        session.add(
            GeneratedAnalysis(
                analysis_type=analysis_type,
                analysis_key=analysis_key,
                output_json=serialized,
                evidence_fingerprint=fingerprint,
            )
        )


def refresh_derived_analysis(session: Session) -> None:
    fingerprint = current_evidence_fingerprint(session)
    guide = build_guide_analysis(session)
    insights = build_insights_analysis(session)

    upsert_generated_analysis(session, "guide", "default", guide, fingerprint)
    upsert_generated_analysis(session, "insights", "default", insights, fingerprint)


def get_guide(session: Session) -> dict:
    fingerprint = current_evidence_fingerprint(session)
    cached = session.scalar(
        select(GeneratedAnalysis).where(
            GeneratedAnalysis.analysis_type == "guide",
            GeneratedAnalysis.analysis_key == "default",
        )
    )
    if cached and cached.evidence_fingerprint == fingerprint:
        return json.loads(cached.output_json)

    output = build_guide_analysis(session)
    upsert_generated_analysis(session, "guide", "default", output, fingerprint)
    session.commit()
    return output


def get_insights(session: Session) -> dict:
    fingerprint = current_evidence_fingerprint(session)
    cached = session.scalar(
        select(GeneratedAnalysis).where(
            GeneratedAnalysis.analysis_type == "insights",
            GeneratedAnalysis.analysis_key == "default",
        )
    )
    if cached and cached.evidence_fingerprint == fingerprint:
        return json.loads(cached.output_json)

    output = build_insights_analysis(session)
    upsert_generated_analysis(session, "insights", "default", output, fingerprint)
    session.commit()
    return output


def answer_question(
    session: Session,
    question: str,
    transcript_id: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
):
    evidence = HybridRetriever(session).retrieve(
        question,
        transcript_id=transcript_id,
        limit=8,
    )
    return generate_grounded_answer(
        question=question,
        evidence=evidence,
        session=session,
        request_api_key=api_key,
        request_model=model,
    )