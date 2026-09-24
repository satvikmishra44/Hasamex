from pathlib import Path

from backend.parser import parse_transcript

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_parses_expert_metadata_and_preserves_text():
    parsed = parse_transcript(RAW / "Transcript_1_France.txt")

    assert parsed.expert_name == "Dr. Jean Martin"
    assert parsed.expert_role == "Head of Urology"
    assert parsed.market_name == "France"
    assert parsed.market_code == "FR"
    assert parsed.is_incomplete is False

    turn = next(item for item in parsed.turns if item.chunk_id == "FR-02:18")
    assert turn.timestamp == "02:18"
    assert turn.speaker == "Dr. Martin"
    assert turn.preceding_question == "So ROI is important?"
    assert turn.text.startswith("Very important.")
    assert "maintenance cost" in turn.text


def test_identifies_incomplete_sources():
    germany = parse_transcript(RAW / "Transcript_2_Germany.txt")
    uk = parse_transcript(RAW / "Transcript_3_UK.txt")

    assert germany.is_incomplete is True
    assert uk.is_incomplete is True

    germany_last = next(item for item in germany.turns if item.chunk_id == "DE-04:09")
    uk_last = next(item for item in uk.turns if item.chunk_id == "UK-04:06")

    assert germany_last.text.endswith("gradual,")
    assert uk_last.text.endswith("and")


def test_creates_stable_market_timestamp_chunk_ids():
    france = parse_transcript(RAW / "Transcript_1_France.txt")
    germany = parse_transcript(RAW / "Transcript_2_Germany.txt")
    uk = parse_transcript(RAW / "Transcript_3_UK.txt")

    france_ids = [item.chunk_id for item in france.turns if item.chunk_id]
    germany_ids = [item.chunk_id for item in germany.turns if item.chunk_id]
    uk_ids = [item.chunk_id for item in uk.turns if item.chunk_id]

    assert "FR-00:18" in france_ids
    assert "FR-06:08" in france_ids
    assert "DE-02:08" in germany_ids
    assert "DE-04:09" in germany_ids
    assert "UK-03:10" in uk_ids
    assert "UK-04:06" in uk_ids