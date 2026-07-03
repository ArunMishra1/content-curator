# Design Decisions

## Contents

- [Embeddings: local model, not an API](#embeddings-local-model-not-an-api)
- [Summarization: once, at ingest time, never at query time](#summarization-once-at-ingest-time-never-at-query-time)
- [Model choice for summarization: Haiku, not a larger model](#model-choice-for-summarization-haiku-not-a-larger-model)
- [Chunk size: 500 characters, 50 character overlap](#chunk-size-500-characters-50-character-overlap)
- [doc_id: deterministic hash of the URL, not a random ID](#doc_id-deterministic-hash-of-the-url-not-a-random-id)
- [Chunk-to-document aggregation: best chunk score, not average](#chunk-to-document-aggregation-best-chunk-score-not-average)
- [Ranking is pure vector similarity — a known, accepted limitation](#ranking-is-pure-vector-similarity--a-known-accepted-limitation)
- [Singletons for the embedder and vector store](#singletons-for-the-embedder-and-vector-store)
- [Auth: one static API key, not JWT/OAuth2](#auth-one-static-api-key-not-jwtoauth2)
- [Rate limiting: keyed by API key, not IP address](#rate-limiting-keyed-by-api-key-not-ip-address)
- [Per-doc_id locking, not request coalescing](#per-doc_id-locking-not-request-coalescing)
- [Batch ingestion never fails all-or-nothing](#batch-ingestion-never-fails-all-or-nothing)

This file records *why*, not *what* — for the structure itself, see `ARCHITECTURE.md`.

## Embeddings: local model, not an API

Chosen deliberately for the MVP stage: zero cost, no API key friction, works
offline, and quality is good enough to prove retrieval works. The
`EmbeddingProvider` abstract class exists specifically so this can change
later (e.g. to OpenAI or Voyage for better quality) without touching
`src/chunking.py`, `src/vectorstore.py`, or `src/pipeline.py` — only `src/embeddings.py` and
one line of config would change.

## Summarization: once, at ingest time, never at query time

The naive approach — summarize on every `/recommend` call — multiplies LLM
cost and latency by every search a user ever makes. Summarizing once when
content is added and storing the result means `/recommend` is a pure vector
lookup: fast and free after ingestion.

## Model choice for summarization: Haiku, not a larger model

Summarizing is bulk, repetitive, low-reasoning work done once per document.
Paying for a larger model here buys no meaningful quality improvement for
this specific task and would multiply cost across every ingested URL.

## Chunk size: 500 characters, 50 character overlap

Too small and chunks lose surrounding context (embeddings become noisy
word-soup). Too large and a chunk blurs multiple topics into one vector that
doesn't match any specific query well. ~500 characters is roughly one
paragraph — small enough to be about one idea, large enough to carry context.
The 50-character overlap prevents a sentence from being cut in half at a
chunk boundary and losing meaning on both sides.

## doc_id: deterministic hash of the URL, not a random ID

Same URL always produces the same `doc_id`. This is what makes ChromaDB's
`upsert` behavior meaningful — re-ingesting a URL updates the existing entry
in place instead of creating a duplicate under a new ID.

## Chunk-to-document aggregation: best chunk score, not average

A document with one highly relevant paragraph should rank highly even if
the rest of the document covers something else. Averaging would dilute that
signal; taking the best-matching chunk's score preserves it.

## Ranking is pure vector similarity — a known, accepted limitation

Embedding a profile like "VP of Engineering, 30 minutes" against content
chunks matches on topic/wording, not reading difficulty or time budget. A
highly technical paper can outrank a well-written primer on the same topic.
Accepted for v1; tracked as the open problem in `TODO.md`.

## Singletons for the embedder and vector store

Loading the embedding model takes a noticeable moment. `src/pipeline.py` and
`src/main.py` create it once (`get_embedder()`) and reuse it everywhere, rather
than reloading per call — this matters more once the API is serving many
requests than it does for a single script run.

## Auth: one static API key, not JWT/OAuth2

There is exactly one trust boundary right now — "has the key" vs. "doesn't"
— not multiple users needing different permissions. Building session/token
infrastructure for a permission model that doesn't exist yet is complexity
with no current payoff. Contained in `src/auth.py`; upgrading to per-user keys
later wouldn't require touching the endpoints, only how `verify_api_key`
resolves a key to a caller.

## Rate limiting: keyed by API key, not IP address

IP-based limiting (the library default) is the wrong unit here: multiple
legitimate callers can share an IP (behind NAT), and a bad actor can rotate
IPs trivially. Every caller already sends an API key, so that's the correct
identity to throttle on. Known consequence: because there's currently only
one valid key for the whole app, all callers share one global rate-limit
budget — a real constraint if the key is ever shared with more than one
consumer of the API.

## Per-doc_id locking, not request coalescing

Two concurrent requests to ingest the same URL could otherwise both write to
the vector store around the same time, risking corrupted/interleaved data.
A lock per `doc_id` serializes writes for that document, fixing correctness.
It does NOT fix efficiency — the second request still redoes the full
extraction + summarization work once the lock releases, wasting one Claude
API call in that scenario. Real fix for the efficiency side would be request
coalescing (second caller waits for and reuses the first call's result) —
deliberately not built, since it's real added complexity not justified at
current traffic levels.

## Batch ingestion never fails all-or-nothing

`ingest_urls()` processes a list and gives every URL its own result —
success or a specific failure reason — rather than raising on the first bad
URL and losing the rest. A 20-URL batch with 1 dead link should produce 19
successes and 1 clearly reported failure, not a crashed process.
