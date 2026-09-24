# Architecture

## Purpose

Expert Call Intelligence is a single-process FastAPI application designed to demonstrate evidence-grounded research workflows without unnecessary infrastructure.

The design separates source storage, retrieval, generation, validation, and presentation so each grounding boundary remains visible and testable.

## Components

### Raw source layer

Four text files live in `backend/data/raw/`:

- One interview guide
- One France transcript
- One Germany transcript
- One United Kingdom transcript

The application never searches the web or adds outside market information.

### Parser

The parser extracts:

- Expert identity and role
- Market and market code
- Timestamped turns
- Speaker
- Exact source text
- Preceding interviewer question
- Stable turn order
- Incomplete-source status

Each expert answer receives a stable ID combining market code and timestamp, such as `FR-02:18`.

### SQLite

SQLite is the source of truth for:

- Full transcript metadata
- Exact transcript turns
- Stable chunk IDs
- Raw transcript content
- Ingestion hashes
- Ingestion-run status

Quotes displayed in the UI always originate from SQLite.

### ChromaDB

Only expert-answer chunks are indexed. The application creates embeddings with:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Chroma stores the vector, source text, and source metadata. The persistent directory is `backend/data/chroma/`.

### Hybrid retrieval

A query is ranked using:

1. Chroma semantic similarity
2. BM25-style lexical relevance
3. Concept-focused query expansion
4. Weighted score fusion
5. Transcript-aware diversity selection

One-call queries apply a transcript filter before ranking.

### Optional generation

If Gemini is configured, the service receives only the retrieved evidence. It is instructed to treat transcript text as data and return schema-constrained JSON.

If Gemini is unavailable, deterministic local retrieval mode returns stored evidence without pretending that a model produced a synthesis.

## Data flow

```text
Raw files
  → parser
  → SQLite transcript and turn records
  → local embedding model
  → persistent Chroma collection

User query
  → scope filter
  → lexical + semantic retrieval
  → evidence threshold
  → optional Gemini generation
  → citation validation
  → SQLite quote hydration
  → browser response
```

## Citation validation

The validation boundary performs four checks:

1. Every generated claim has at least one citation.
2. Every cited ID belongs to the retrieved evidence set.
3. Every cited ID resolves to an expert-answer row in SQLite.
4. Citation-like IDs appearing in the generated answer are also valid.

Invalid output is never sent directly to the browser. The service retries once with a correction instruction. A second failure triggers deterministic fallback.

The model does not author final quote strings. The API hydrates exact quotes, timestamps, experts, roles, and markets from SQLite after validation.

## Incomplete transcripts

The parser recognizes the explicit metadata note in Germany and UK source files. Both transcripts are marked incomplete.

The final Germany and UK expert turns are stored exactly as supplied. No service appends punctuation or inferred continuation.

## API-key override

The frontend Settings panel can send a temporary Gemini API key and model with a chat request.

Priority is:

1. Frontend request key and model
2. Server `.env` key and model
3. Local retrieval mode

The request credential is not returned, persisted, or added to application logs. This is convenient for a local case-study demo. Production systems should keep credentials on a trusted server.

## Design tradeoffs

### SQLite instead of PostgreSQL

SQLite keeps setup simple and provides transactional source storage. PostgreSQL becomes appropriate for concurrent users, larger corpora, access control, and operational reporting.

### Chroma instead of a hosted store

Persistent local Chroma avoids hosted dependencies and embedding API costs. At greater scale, pgvector or a managed vector system may simplify operations.

### Deterministic guide and insights

The interview guide and known cross-call insights use explicit evidence mappings. This avoids repeated model calls and guarantees predictable demonstrations.

### Expert-answer chunks only

Short timestamp-aligned expert answers retain citation precision. Interviewer questions remain in SQLite and are added to vector metadata as retrieval context.

## Scaling path

For 30 or more calls:

- Process ingestion asynchronously
- Add durable ingestion jobs and retries
- Store sources in PostgreSQL or object storage
- Introduce pgvector or a managed vector index
- Add a cross-encoder reranker
- Cache common guide and comparison outputs
- Create labelled retrieval and answer-quality evaluations
- Track model latency, cost, citation failures, and empty retrieval
- Add authentication, workspaces, and row-level isolation
- Encrypt server-managed credentials
- Add human approval for externally distributed findings