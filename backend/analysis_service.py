from sqlalchemy.orm import Session

from backend.citation_service import get_citations
from backend.gemini_service import generate_grounded_answer
from backend.retrieval import HybridRetriever

GUIDE = [
    {
        "number": 1,
        "question": "How would you describe current adoption of robotic surgery in your market?",
        "answers": {
            "FR": {
                "summary": "Adoption is growing but remains concentrated in larger academic hospitals and better-funded private centres.",
                "coverage": "sufficient",
                "ids": ["FR-00:18"],
            },
            "DE": {
                "summary": "Adoption is growing unevenly, with university hospitals ahead of smaller hospitals.",
                "coverage": "sufficient",
                "ids": ["DE-00:16"],
            },
            "UK": {
                "summary": "Adoption is increasing, with robotic surgery becoming standard for selected procedures in some larger NHS trusts, while access varies.",
                "coverage": "sufficient",
                "ids": ["UK-00:14"],
            },
        },
    },
    {
        "number": 2,
        "question": "What are the main barriers to adoption?",
        "answers": {
            "FR": {
                "summary": "Capital budget approval is the primary barrier, and purchasing committees require a strong economic case.",
                "coverage": "sufficient",
                "ids": ["FR-01:20"],
            },
            "DE": {
                "summary": "Large capital cost and uncertainty about sufficient system utilization are the main barriers.",
                "coverage": "sufficient",
                "ids": ["DE-01:10"],
            },
            "UK": {
                "summary": "Funding and training capacity are both important; adoption can stall without enough trained surgeons and theatre staff.",
                "coverage": "sufficient",
                "ids": ["UK-01:05"],
            },
        },
    },
    {
        "number": 3,
        "question": "How important are hospital budgets and ROI in purchasing decisions?",
        "answers": {
            "FR": {
                "summary": "ROI is very important. Finance teams examine utilization, procedure volume, maintenance cost, and payback, especially when clinical outcomes are similar.",
                "coverage": "sufficient",
                "ids": ["FR-02:18", "FR-04:08"],
            },
            "DE": {
                "summary": "Procurement evaluates total ownership cost, procedure volume, maintenance, service, and training; the economic case determines approval.",
                "coverage": "sufficient",
                "ids": ["DE-02:08"],
            },
            "UK": {
                "summary": "ROI matters, but hospitals balance economics with patient outcomes, length of stay, recruitment, and clinical strategy.",
                "coverage": "sufficient",
                "ids": ["UK-02:07", "UK-03:10"],
            },
        },
    },
    {
        "number": 4,
        "question": "How important are surgeon training and clinical outcomes?",
        "answers": {
            "FR": {
                "summary": "Training multiple surgeons supports utilization and economics. Clinical outcomes are necessary but not sufficient on their own.",
                "coverage": "sufficient",
                "ids": ["FR-03:10", "FR-04:08"],
            },
            "DE": {
                "summary": "Training is operationally important because reliance on one comfortable surgeon weakens utilization and the business case.",
                "coverage": "sufficient",
                "ids": ["DE-03:05"],
            },
            "UK": {
                "summary": "Training capacity is as important as funding because both surgeons and theatre staff must be trained for adoption to progress.",
                "coverage": "sufficient",
                "ids": ["UK-01:05"],
            },
        },
    },
    {
        "number": 5,
        "question": "What adoption trend do you expect over the next 3–5 years?",
        "answers": {
            "FR": {
                "summary": "The expert expects continued, steady rather than explosive adoption, with smaller hospitals remaining slower.",
                "coverage": "sufficient",
                "ids": ["FR-05:07"],
            },
            "DE": {
                "summary": "The supplied evidence indicates gradual rather than dramatic growth, but the source ends mid-sentence.",
                "coverage": "partial",
                "ids": ["DE-04:09"],
            },
            "UK": {
                "summary": "The expert is positive and says adoption could accelerate if training expands, but the source ends mid-sentence.",
                "coverage": "partial",
                "ids": ["UK-04:06"],
            },
        },
    },
    {
        "number": 6,
        "question": "What is the typical hospital decision-making timeline for purchasing a new robotic system?",
        "answers": {
            "FR": {
                "summary": "Six to twelve months is realistic once a hospital becomes serious, with possible delay into a later budget cycle.",
                "coverage": "sufficient",
                "ids": ["FR-06:08"],
            },
            "DE": {
                "summary": "No evidence for this question in the supplied Germany call.",
                "coverage": "insufficient",
                "ids": [],
            },
            "UK": {
                "summary": "No evidence for this question in the supplied United Kingdom call.",
                "coverage": "insufficient",
                "ids": [],
            },
        },
    },
]

INSIGHTS = {
    "shared_themes": [
        {
            "category": "Shared theme",
            "title": "Adoption is growing but uneven",
            "explanation": "All three calls describe increasing adoption. Each also identifies uneven access or slower adoption outside larger or more advanced hospitals.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-00:18", "DE-00:16", "UK-00:14"],
        },
        {
            "category": "Shared theme",
            "title": "Economics and utilization shape approval",
            "explanation": "France and Germany explicitly connect approval to economics and utilization. The UK also considers ROI, while balancing it with clinical and strategic factors.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-02:18", "DE-02:08", "UK-02:07"],
        },
        {
            "category": "Shared theme",
            "title": "Training affects utilization",
            "explanation": "Each expert links training capacity to practical adoption. France and Germany directly connect the number of trained surgeons to utilization and the business case.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-03:10", "DE-03:05", "UK-01:05"],
        },
        {
            "category": "Shared theme",
            "title": "Growth continues, with different intensity",
            "explanation": "France expects steady growth and Germany expects gradual growth. The UK is more positive and describes conditional acceleration if training expands.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-05:07", "DE-04:09", "UK-04:06"],
        },
    ],
    "differences": [
        {
            "category": "Difference in emphasis",
            "title": "Approval gate versus balanced strategy",
            "explanation": "France and Germany present economics as a decisive approval gate. The UK expert instead describes economics and clinical strategy as balanced.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-04:08", "DE-02:08", "UK-03:10"],
        },
        {
            "category": "Difference in emphasis",
            "title": "Different barrier priorities",
            "explanation": "France emphasizes capital approval, Germany emphasizes cost and sufficient utilization, and the UK gives training capacity equal importance with funding.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-01:20", "DE-01:10", "UK-01:05"],
        },
        {
            "category": "Difference in emphasis",
            "title": "Conditional optimism in the UK",
            "explanation": "France and Germany describe steady or gradual growth. The UK expert is more optimistic, conditional on expanded training.",
            "countries": ["France", "Germany", "United Kingdom"],
            "ids": ["FR-05:07", "DE-04:09", "UK-04:06"],
        },
    ],
}


def get_guide(session: Session) -> dict:
    output = []
    for question in GUIDE:
        answers = []
        for market_code, answer in question["answers"].items():
            citations = get_citations(session, answer["ids"])
            market = {
                "FR": "France",
                "DE": "Germany",
                "UK": "United Kingdom",
            }[market_code]
            answers.append(
                {
                    "market_code": market_code,
                    "market": market,
                    "summary": answer["summary"],
                    "coverage": answer["coverage"],
                    "citations": [item.model_dump() for item in citations],
                }
            )
        output.append(
            {
                "number": question["number"],
                "question": question["question"],
                "answers": answers,
            }
        )
    return {"questions": output}


def get_insights(session: Session) -> dict:
    output: dict[str, list[dict]] = {}
    for group, insights in INSIGHTS.items():
        output[group] = []
        for insight in insights:
            citations = get_citations(session, insight["ids"])
            output[group].append(
                {
                    **insight,
                    "citations": [item.model_dump() for item in citations],
                }
            )
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