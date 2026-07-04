# Design Decisions

## Contents

- [Ranking: profession-aware LLM re-ranking, not pure vector similarity](#ranking-profession-aware-llm-re-ranking-not-pure-vector-similarity)
- [Embeddings: local model, not an API](#embeddings-local-model-not-an-api)
- [Summarization: once, at ingest time, never at query time](#summarization-once-at-ingest-time-never-at-query-time)
- [Model choice for summarization: Haiku, not a larger model](#model-choice-for-summarization-haiku-not-a-larger-model)
- [Chunk size: 500 characters, 50 character overlap](#chunk-size-500-characters-50-character-overlap)
- [doc_id: deterministic hash of the URL, not a random ID](#doc_id-deterministic-hash-of-the-url-not-a-random-id)
- [Chunk-to-document aggregation: best chunk score, not average](#chunk-to-document-aggregation-best-chunk-score-not-average)
- [Ranking is pure vector similarity — superseded](#ranking-is-pure-vector-similarity--superseded)
- [Singletons for the embedder and vector store](#singletons-for-the-embedder-and-vector-store)
- [Auth: one static API key, not JWT/OAuth2](#auth-one-static-api-key-not-jwtoauth2)
- [Rate limiting: keyed by API key, not IP address](#rate-limiting-keyed-by-api-key-not-ip-address)
- [Per-doc_id locking, not request coalescing](#per-doc_id-locking-not-request-coalescing)
- [Batch ingestion never fails all-or-nothing](#batch-ingestion-never-fails-all-or-nothing)
- [Data durability: manual backup script, not a database migration](#data-durability-manual-backup-script-not-a-database-migration)

This file records *why*, not *what* — for the structure itself, see `ARCHITECTURE.md`.

## Ranking: profession-aware LLM re-ranking, not pure vector similarity

**This reverses part of the "no LLM at query time" position stated below**
("Summarization: once, at ingest time, never at query time") — worth being
explicit about, since silently contradicting a documented principle is
exactly the kind of thing that erodes trust in these docs.

Pure vector similarity (the original v1 approach) matches on topic and
vocabulary overlap, not on what a specific reader actually needs — a
VP of Engineering and a PhD researcher asking about the same topic got
identical rankings, because "similar wording" was the only signal. Fixed by
adding a second stage: vector search still retrieves a broad candidate pool
by topic (unchanged, still cheap, still no LLM), but a Claude Haiku call
then reasons about which candidates actually fit *this reader's* expertise
level, time constraints, and likely use for the information, and orders them
accordingly. See `ranker.py`.

Why this tradeoff was accepted despite conflicting with the earlier
principle: the earlier principle was about avoiding *repeated, avoidable*
LLM cost (summarizing on every query would multiply cost per search).
Re-ranking is a different situation — the reasoning genuinely has to happen
per-query, because it depends on the reader's specific profile, which is
different every time. There's no way to precompute "the right answer for
every possible profession" at ingest time without inventing a rigid
taxonomy that would fail on any profile that doesn't fit a predefined box
(this was seriously considered — see the ingest-time-tagging alternatives
that were evaluated and rejected, in project discussion history).

Cost is controlled two ways: the candidate pool sent to the LLM is capped
(`MAX_CANDIDATES` in `ranker.py`) regardless of how large `top_n` is
requested, and only short summaries are sent, never full document text.
`/recommend`'s rate limit was tightened from 60/min to 20/min to reflect
that this endpoint now has a real cost per call, where it didn't before.

Failure handling follows the same pattern established for summarization
failures: if the re-rank call fails or returns something unparseable, the
endpoint falls back to plain vector-similarity order rather than failing
the whole request — a visible `[WARNING]` is printed either way, consistent
with this project's rule against silent failure.

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

## Ranking is pure vector similarity — superseded

This was the v1 limitation: matching a profile like "VP of Engineering,
30 minutes" against content chunks matched on topic/wording, not reading
difficulty or time budget. **Superseded** by the LLM re-ranking stage
described at the top of this file — vector similarity is still the first
retrieval pass, but it's no longer the final ranking. Left here, marked
superseded rather than deleted, so the reasoning trail for why this was a
real limitation (and what specifically was fixed) stays intact.

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

## Data durability: manual backup script, not a database migration

`chroma_data/` is a single local file with no built-in backup or
multi-instance support. Two genuinely separate problems get bundled under
that description: **durability** (losing the disk = losing everything) and
**multi-instance access** (running more than one server, all sharing data).

Four options were compared: (1) a scheduled backup script copying
`chroma_data/` elsewhere, (2) running ChromaDB in client-server mode so
multiple app instances share one Chroma process, (3) migrating to a managed
vector database (Chroma Cloud, Pinecone, Qdrant, etc.), (4) migrating to
Postgres with the `pgvector` extension, unifying vector and relational
storage.

Chose (1). Reasoning: this project currently has exactly one real risk —
losing a laptop's disk — not a multi-instance requirement. Options 2-4 all
solve problems that don't exist yet (running multiple server copies, a
growing relational data model) at real cost (new infrastructure to run and
monitor, or real migration effort). Building for a scaling need before it
exists is the same mistake as the ingest-time tagging taxonomy that was
evaluated and rejected for ranking — solving a hypothetical future problem
at real present cost. `scripts/backup_chroma.sh` and
`scripts/restore_chroma.sh` handle the actual current risk in about 15
minutes of setup.

Explicitly NOT solved by this: multi-instance deployment. If this project
ever needs to run more than one server copy — real user growth, uptime
requirements — that's the point to revisit options 2-4, not before. Also
worth naming: a backup script only protects against disk failure if its
destination is actually off the original machine (a cloud-synced folder,
not a different folder on the same disk) — the script warns explicitly if
misconfigured to write inside the project's own directory.
