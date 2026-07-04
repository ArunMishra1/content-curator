# Architecture

## Contents

- [Overview](#overview)
- [Component responsibilities](#component-responsibilities)
- [Data model](#data-model)
- [Content classification](#content-classification)
- [Why these specific tradeoffs](#why-these-specific-tradeoffs)

## Overview

The system has two flows: **ingest** (get content into the index) and
**recommend** (get ranked content back out). Both are exposed over HTTP via
FastAPI, but the underlying logic is decoupled from the API layer — `src/pipeline.py`
and `src/vectorstore.py` work standalone, callable from a script, a test, or the API.

```
INGEST FLOW
  URL
   |
   v
[src/extractors/web.py or src/extractors/youtube.py]  -- fetch + clean text
   |
   v
[src/chunking.py]  -- split into ~500-char overlapping pieces
   |
   v
[src/summarizer.py]  -- one Claude Haiku call, ONCE per document
   |
   v
[src/embeddings.py]  -- local model, text -> 384-dim vector, per chunk
   |
   v
[src/vectorstore.py]  -- store chunks + vectors + metadata in ChromaDB


RECOMMEND FLOW
  profile text ("VP of Engineering, 30 min on LLMs")
   |
   v
[src/embeddings.py]  -- embed the profile text the same way as chunks
   |
   v
[src/vectorstore.py]  -- cosine similarity search, broad candidate pool (~15-20 docs)
   |
   v
  collapse chunks -> parent documents, keep best score per doc
   |
   v
[src/ranker.py]  -- Claude Haiku reasons about THIS reader's profession,
   |                expertise, and time constraints; reorders and trims
   |                (falls back to plain vector order if this call fails)
   v
  ranked list of documents with title/url/summary/score/reason
```

## Component responsibilities

All files below live under `src/` (except `tests/`, which sits at the repo root alongside documentation and config).

| File | Responsibility | Key design choice |
|---|---|---|
| `src/models.py` | Shared data shapes (`ExtractedContent`, `Chunk`, `Document`, `IngestResult`) | One source of truth for field names across all modules |
| `src/embeddings.py` | Text -> vector | Abstract `EmbeddingProvider` interface; local model today, swappable to an API provider later without touching callers |
| `src/extractors/web.py` | Webpage -> clean text | Uses `trafilatura` to strip nav/ads/comments — not a generic HTML parser |
| `src/extractors/youtube.py` | YouTube video -> transcript text | Separate code path from web articles; different failure modes (captions disabled, region-locked) |
| `src/chunking.py` | Long text -> overlapping ~500-char pieces | Small enough per-chunk embeddings stay precise; overlap prevents mid-sentence cuts losing meaning |
| `src/summarizer.py` | Document -> short AI summary | Runs ONCE at ingest time, never at query time (cost/latency control); Claude Haiku, not a larger model, since summarizing is bulk/low-reasoning work |
| `src/vectorstore.py` | Store + search vectors | Wraps ChromaDB; collapses chunk-level matches to document-level rankings, keeping each doc's best-scoring chunk |
| `src/ranker.py` | Profession-aware re-ranking | Second-stage LLM reasoning pass over the broad candidate pool; Claude Haiku, capped candidate count, falls back to plain vector order on failure |
| `src/discover.py` | Find candidate URLs for a topic | Wraps the Tavily search API; deliberately does NOT ingest results — see `DESIGN.md` |
| `src/pipeline.py` | Orchestrates ingest end-to-end | Deterministic `doc_id` (hash of URL) enables safe upsert on re-ingestion; per-`doc_id` lock prevents concurrent-request races; batch ingestion isolates per-URL failures |
| `src/auth.py` | API key verification | Single static key via `X-API-Key` header, timing-safe comparison |
| `src/main.py` | HTTP layer | FastAPI app; loads the embedding model at startup (not per-request); rate limits `/ingest` (10/min) and `/recommend` (20/min — tightened from 60/min once `/recommend` started making a real LLM call), keyed by API key |

## Data model

A **Document** is the user-facing unit (one URL = one document, with a title,
summary, and URL). A **Chunk** is the storage/search unit (a document has many
chunks). This split exists because embeddings work best on small, focused text,
but users think and want results in terms of whole articles, not paragraph
fragments. The vector store's `query()` method is the bridge: it searches at
chunk granularity, then re-aggregates to document granularity before returning
results.

## Content classification

Every ingested item still has only a `source_type` field (`article` or
`youtube`) — no stored topic taxonomy, difficulty tags, or profession labels
on documents. Profession/difficulty-awareness in ranking is instead solved
at query time by `ranker.py` reasoning fresh over each request's specific
profile, rather than by tagging content in advance (see `DESIGN.md` for why
tagging was considered and not chosen). This means there's still no
persistent classification of *what audience a piece of content suits* —
only a per-query judgment. If a real content taxonomy is ever built
(e.g., for browsing/filtering by category independent of a search), it
would live as additional metadata fields on `Document`, set during
ingestion — either by extending the summarizer's prompt or a separate
classification step. See `TAXONOMY.md`.

## Why these specific tradeoffs

See `DESIGN.md` for the reasoning behind individual choices (chunk size,
local vs. API embeddings, singleton pattern, etc.) — this file is about
structure, that one is about *why* the structure looks this way.
