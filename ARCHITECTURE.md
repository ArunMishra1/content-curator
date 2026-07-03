# Architecture

## Contents

- [Overview](#overview)
- [Component responsibilities](#component-responsibilities)
- [Data model](#data-model)
- [Content classification (not yet built)](#content-classification-not-yet-built)
- [Why these specific tradeoffs](#why-these-specific-tradeoffs)

## Overview

The system has two flows: **ingest** (get content into the index) and
**recommend** (get ranked content back out). Both are exposed over HTTP via
FastAPI, but the underlying logic is decoupled from the API layer — `pipeline.py`
and `vectorstore.py` work standalone, callable from a script, a test, or the API.

```
INGEST FLOW
  URL
   |
   v
[extractors/web.py or extractors/youtube.py]  -- fetch + clean text
   |
   v
[chunking.py]  -- split into ~500-char overlapping pieces
   |
   v
[summarizer.py]  -- one Claude Haiku call, ONCE per document
   |
   v
[embeddings.py]  -- local model, text -> 384-dim vector, per chunk
   |
   v
[vectorstore.py]  -- store chunks + vectors + metadata in ChromaDB


RECOMMEND FLOW
  profile text ("VP of Engineering, 30 min on LLMs")
   |
   v
[embeddings.py]  -- embed the profile text the same way as chunks
   |
   v
[vectorstore.py]  -- cosine similarity search, top-K chunks
   |
   v
  collapse chunks -> parent documents, keep best score per doc
   |
   v
  ranked list of documents with title/url/summary/score
```

## Component responsibilities

| File | Responsibility | Key design choice |
|---|---|---|
| `models.py` | Shared data shapes (`ExtractedContent`, `Chunk`, `Document`, `IngestResult`) | One source of truth for field names across all modules |
| `embeddings.py` | Text -> vector | Abstract `EmbeddingProvider` interface; local model today, swappable to an API provider later without touching callers |
| `extractors/web.py` | Webpage -> clean text | Uses `trafilatura` to strip nav/ads/comments — not a generic HTML parser |
| `extractors/youtube.py` | YouTube video -> transcript text | Separate code path from web articles; different failure modes (captions disabled, region-locked) |
| `chunking.py` | Long text -> overlapping ~500-char pieces | Small enough per-chunk embeddings stay precise; overlap prevents mid-sentence cuts losing meaning |
| `summarizer.py` | Document -> short AI summary | Runs ONCE at ingest time, never at query time (cost/latency control); Claude Haiku, not a larger model, since summarizing is bulk/low-reasoning work |
| `vectorstore.py` | Store + search vectors | Wraps ChromaDB; collapses chunk-level matches to document-level rankings, keeping each doc's best-scoring chunk |
| `pipeline.py` | Orchestrates ingest end-to-end | Deterministic `doc_id` (hash of URL) enables safe upsert on re-ingestion; per-`doc_id` lock prevents concurrent-request races; batch ingestion isolates per-URL failures |
| `auth.py` | API key verification | Single static key via `X-API-Key` header, timing-safe comparison |
| `main.py` | HTTP layer | FastAPI app; loads the embedding model at startup (not per-request); rate limits `/ingest` (10/min) and `/recommend` (60/min), keyed by API key |

## Data model

A **Document** is the user-facing unit (one URL = one document, with a title,
summary, and URL). A **Chunk** is the storage/search unit (a document has many
chunks). This split exists because embeddings work best on small, focused text,
but users think and want results in terms of whole articles, not paragraph
fragments. The vector store's `query()` method is the bridge: it searches at
chunk granularity, then re-aggregates to document granularity before returning
results.

## Content classification (not yet built)

Right now every ingested item has only a `source_type` field (`article` or
`youtube`) — no topic taxonomy, difficulty level, or profession-relevance
tagging. Ranking is pure vector similarity between the profile text and
content chunks, which matches on *topic* but not on *reading level* or
*role-relevance* (this is the open problem tracked in `TODO.md`). If a real
taxonomy is built later (e.g., difficulty tiers, professional domains), it
would likely live as additional metadata fields on `Document` and get set
during ingestion — either by the summarizer's LLM call (extend the prompt to
also classify) or a separate classification step.

## Why these specific tradeoffs

See `DESIGN.md` for the reasoning behind individual choices (chunk size,
local vs. API embeddings, singleton pattern, etc.) — this file is about
structure, that one is about *why* the structure looks this way.
