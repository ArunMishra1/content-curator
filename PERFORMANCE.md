# Performance Notes

## Contents

- [Where time actually goes during ingestion](#where-time-actually-goes-during-ingestion)
- [Where time goes during recommendation](#where-time-goes-during-recommendation)
- [Known bottlenecks and scaling limits](#known-bottlenecks-and-scaling-limits)
- [What hasn't been measured at all](#what-hasnt-been-measured-at-all)

Honest status: **this system has never been load-tested.** Everything below
is based on component-level behavior observed during development, not
benchmarks under real traffic. Treat numbers as rough orders of magnitude,
not guarantees.

## Where time actually goes during ingestion

For a single URL, in rough order of cost:

1. **Fetch + extract** — network-bound, typically under 1 second for a
   normal webpage, more for slow/large pages. YouTube transcript fetch is
   similarly network-bound.
2. **Chunking** — negligible, pure CPU string manipulation.
3. **Summarization** — one Claude Haiku API call, network round-trip plus
   generation time. This is the main latency cost per document and the main
   per-document dollar cost.
4. **Embedding** — local model inference, CPU-bound. Fast per chunk, but a
   long document produces many chunks (observed: ~180 chunks for one
   full Wikipedia article), so total embedding time scales with document
   length, not just count of documents.
5. **Storage** — ChromaDB write, fast, local disk.

## Where time goes during recommendation

Much cheaper than ingestion: one embedding call (the profile text), one
ChromaDB similarity search, no LLM call at all. This asymmetry is
deliberate — see `DESIGN.md` on why summarization happens at ingest time,
not query time.

## Known bottlenecks and scaling limits

- **Embedding model loads once at server startup**, which is good for
  request latency but means every server restart pays that cost again
  before the first request can be served.
- **`chunks_to_scan` scales with index size** (fixed in the 2026-07-03
  update), but this means recommendation queries get slightly more
  expensive as the index grows, since more candidate chunks are considered
  per search. Not yet measured at what index size this becomes noticeable.
- **ChromaDB is a single local file (`chroma_data/`)** — no sharding, no
  replication, no concurrent-write guarantees beyond what SQLite-backed
  storage provides underneath. Fine for one process on one machine; not a
  multi-instance-safe design (tracked in `TODO.md`).
- **`uvicorn --reload` (used throughout development) is a single-process dev
  server** — not representative of production throughput. No load testing
  has been done with a production ASGI setup (multiple workers, gunicorn,
  etc.).
- **Per-`doc_id` locking (added 2026-07-03) serializes concurrent ingestion
  of the same URL** — correct, but means if the same popular URL is
  submitted by many concurrent callers, they queue up rather than run in
  parallel. Not a concern unless a single URL is ingested very frequently
  and concurrently.
- **Rate limits (10/min ingest, 60/min recommend) are shared across all
  callers of the single API key** — see `DESIGN.md`. This is a throughput
  ceiling on the whole app, not per-user.

## What hasn't been measured at all

- Behavior under concurrent load beyond the 5-thread test used to verify
  the locking fix.
- Memory usage as the ChromaDB index grows into the thousands of documents.
- Cold-start latency in a real deployment environment (vs. a local laptop
  with the model already cached on disk).
- Actual dollar cost per 1,000 ingested URLs (would require: Claude Haiku
  pricing x average document length x observed token usage — not yet
  calculated).

If any of these become relevant (e.g. before a real launch), that's the
list of what to actually measure before optimizing anything.
