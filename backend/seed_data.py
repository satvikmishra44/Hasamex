from backend.ingestion import run_ingestion


def main() -> None:
    result = run_ingestion()
    print("\nExpert Call Intelligence — ingestion complete")
    print("-" * 48)
    print(f"Files read:                  {result['files_read']}")
    print(f"Transcripts created:         {result['transcripts_created']}")
    print(f"Transcripts updated:         {result['transcripts_updated']}")
    print(f"Expert turns indexed:        {result['expert_turns_indexed']}")
    print(f"Vector records created:      {result['vector_records_created']}")
    print(f"Vector records synchronized: {result['vector_records_synchronized']}")
    print(f"Incomplete transcripts:      {result['incomplete_transcripts']}")
    print(result["message"])


if __name__ == "__main__":
    main()