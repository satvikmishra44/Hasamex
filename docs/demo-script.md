# Technical demo script

Target duration: 4–6 minutes.

## Opening — 20 seconds

**Click:** Open `http://localhost:8000`.

**Say:**

“This is Expert Call Intelligence, an evidence-first research assistant for three expert calls on the European robotic surgery market. The product is intentionally built as one FastAPI application with a local SQLite source store, local embeddings, persistent Chroma retrieval, and optional grounded Gemini generation.”

## Overview — 30 seconds

**Click:** Overview.

**Say:**

“The dashboard establishes the source boundary: three calls, a fixed number of indexed expert moments, and two incomplete sources. France is complete. Germany and the UK deliberately end mid-sentence. The application clearly exposes those limitations instead of filling gaps.”

Point to the market comparison and Gemini/vector-store status.

## Interview Guide — 55 seconds

**Click:** Interview Guide.

**Say:**

“The six research questions use deterministic mappings to stored source IDs. This makes the core deliverable predictable and auditable without generating six answers on every page load.”

Scroll through adoption, barriers, economics, and training.

**Click:** Question 6.

**Say:**

“France provides a purchasing timeline. The supporting evidence is `FR-06:08`, where the expert states six to twelve months is realistic.”

**Click:** `FR-06:08` or Open source.

Show the highlighted France turn.

Return to Interview Guide.

**Say:**

“Germany and the UK have no supplied evidence for this question. The system does not estimate their timelines.”

## Cross-call insights — 40 seconds

**Click:** Cross-Call Insights.

**Say:**

“This view separates shared themes from differences in emphasis. All experts describe increasing adoption, while economics, utilization, and training recur across calls. The comparison does not call different emphases contradictions.”

Expand one evidence panel.

**Say:**

“Exact quotes are resolved from stored source turns, and each citation opens the corresponding transcript moment.”

## Ask all calls — 50 seconds

**Click:** Ask All Calls.

**Enter:** `Why does surgeon training affect ROI?`

**Say while loading:**

“The question first runs through hybrid retrieval: local semantic similarity plus lexical ranking. If Gemini is configured, it receives only the retrieved evidence. Otherwise, the app returns a deterministic evidence view.”

After the answer:

“The response reports evidence coverage, generation mode, retrieval scope, and exact supporting sources.”

Optionally ask:

`Which company has the biggest market share?`

**Say:**

“This is outside the supplied evidence, so the system returns the exact refusal: ‘Insufficient evidence in the supplied transcripts.’”

## Ask one call — 35 seconds

**Click:** Ask One Call.

Select France.

**Enter:** `How long does procurement take?`

**Say:**

“The banner confirms that retrieval is restricted to one transcript. France returns `FR-06:08`. Selecting Germany for the same question produces insufficient evidence rather than borrowing France’s answer.”

## Citation deep link — 25 seconds

**Click:** The `FR-06:08` citation.

**Say:**

“The application switches to Transcript Explorer, selects France, scrolls to the precise timestamp, and highlights the source turn. This creates a direct audit trail from answer to source.”

## Data Status — 30 seconds

**Click:** Data Status.

**Say:**

“This operational view shows raw files, parsed calls, indexed expert chunks, local storage paths, embedding model, Gemini configuration, last ingestion, and incomplete-source count.”

**Click:** Refresh data.

**Say:**

“Ingestion is idempotent. It updates SQLite, regenerates changed embeddings, removes stale vector records, and avoids duplicate chunks.”

## Methodology — 45 seconds

**Click:** Methodology.

**Say:**

“The architecture is raw files to a timestamp-aware parser, SQLite source storage, local MiniLM embeddings, persistent Chroma, hybrid retrieval, optional Gemini generation, server-side citation validation, and source-linked answers.”

“Retrieval happens before generation to constrain the model. Gemini cannot author final quotes: quote text is hydrated from SQLite after citation validation. Invalid citation IDs trigger one retry and then a deterministic fallback.”

## Scale explanation — 30 seconds

**Say:**

“To scale from three calls to more than thirty, I would add asynchronous ingestion, PostgreSQL, pgvector or an appropriate managed vector store, caching, reranking, labelled evaluation sets, observability, authentication, workspace isolation, and human review for published findings. The grounding boundary and stable citation model would remain unchanged.”