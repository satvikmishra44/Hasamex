import re
from dataclasses import dataclass
from pathlib import Path

MARKET_CODES = {
    "France": "FR",
    "Germany": "DE",
    "United Kingdom": "UK",
}

TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}$")


@dataclass(frozen=True)
class ParsedTurn:
    timestamp: str
    speaker: str
    text: str
    preceding_question: str | None
    turn_order: int
    is_expert_answer: bool
    chunk_id: str | None


@dataclass(frozen=True)
class ParsedTranscript:
    transcript_id: str
    filename: str
    market_code: str
    market_name: str
    expert_name: str
    expert_role: str
    raw_text: str
    is_incomplete: bool
    turns: list[ParsedTurn]


def parse_transcript(path: str | Path) -> ParsedTranscript:
    source_path = Path(path)
    raw_text = source_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    expert_line = next((line for line in lines if line.startswith("Expert ")), None)
    role_line = next((line for line in lines if line.startswith("Role:")), None)
    market_line = next((line for line in lines if line.startswith("Market:")), None)

    if not expert_line or not role_line or not market_line:
        raise ValueError(f"Missing transcript metadata in {source_path.name}")

    if "–" not in expert_line:
        raise ValueError(f"Expert metadata uses an unexpected format in {source_path.name}")

    expert_name = expert_line.split("–", 1)[1].strip()
    expert_role = role_line.split(":", 1)[1].strip()
    market_name = market_line.split(":", 1)[1].strip()
    market_code = MARKET_CODES.get(market_name)

    if not market_code:
        raise ValueError(f"Unsupported market '{market_name}' in {source_path.name}")

    is_incomplete = "IMPORTANT METADATA NOTE:" in raw_text
    turns: list[ParsedTurn] = []
    preceding_question: str | None = None
    index = 0
    order = 0

    while index < len(lines):
        timestamp = lines[index].strip()
        if not TIMESTAMP_RE.fullmatch(timestamp):
            index += 1
            continue

        index += 1
        content_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index].strip()
            if TIMESTAMP_RE.fullmatch(candidate) or candidate == "IMPORTANT METADATA NOTE:":
                break
            if candidate:
                content_lines.append(candidate)
            index += 1

        if not content_lines:
            continue

        content = " ".join(content_lines)
        if ":" not in content:
            raise ValueError(
                f"Timestamp {timestamp} has no speaker separator in {source_path.name}"
            )

        speaker, text = content.split(":", 1)
        speaker = speaker.strip()
        text = text.strip()
        is_expert = speaker != "Interviewer"
        chunk_id = f"{market_code}-{timestamp}" if is_expert else None

        turns.append(
            ParsedTurn(
                timestamp=timestamp,
                speaker=speaker,
                text=text,
                preceding_question=preceding_question if is_expert else None,
                turn_order=order,
                is_expert_answer=is_expert,
                chunk_id=chunk_id,
            )
        )
        order += 1

        if not is_expert:
            preceding_question = text

        if index < len(lines) and lines[index].strip() == "IMPORTANT METADATA NOTE:":
            break

    if not turns:
        raise ValueError(f"No timestamped turns found in {source_path.name}")

    return ParsedTranscript(
        transcript_id=market_code,
        filename=source_path.name,
        market_code=market_code,
        market_name=market_name,
        expert_name=expert_name,
        expert_role=expert_role,
        raw_text=raw_text,
        is_incomplete=is_incomplete,
        turns=turns,
    )