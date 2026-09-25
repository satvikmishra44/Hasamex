from backend.ingestion import build_raw_corpus_fingerprint, file_hash


def test_same_valid_files_produce_same_fingerprint(tmp_path):
    a = tmp_path / "Transcript_A.txt"
    a.write_text(
        "Expert 1 – A\nRole: Role\nMarket: France\n\n00:00\nInterviewer: Q\n\n00:10\nA: Answer",
        encoding="utf-8",
    )

    valid_files = [(a, file_hash(a))]
    fp1 = build_raw_corpus_fingerprint(valid_files)
    fp2 = build_raw_corpus_fingerprint(valid_files)

    assert fp1 == fp2


def test_changed_file_content_changes_fingerprint(tmp_path):
    a = tmp_path / "Transcript_A.txt"
    a.write_text(
        "Expert 1 – A\nRole: Role\nMarket: France\n\n00:00\nInterviewer: Q\n\n00:10\nA: Answer",
        encoding="utf-8",
    )
    fp1 = build_raw_corpus_fingerprint([(a, file_hash(a))])

    a.write_text(
        "Expert 1 – A\nRole: Role\nMarket: France\n\n00:00\nInterviewer: Q changed\n\n00:10\nA: Answer",
        encoding="utf-8",
    )
    fp2 = build_raw_corpus_fingerprint([(a, file_hash(a))])

    assert fp1 != fp2