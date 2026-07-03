# TODO / Roadmap

## Contents

- [Done](#done)
- [In progress / next up](#in-progress--next-up)
- [Backlog — infrastructure](#backlog--infrastructure)
- [Backlog — content quality](#backlog--content-quality)
- [Backlog — nice to have, not urgent](#backlog--nice-to-have-not-urgent)

## Done

- [x] Core ingest pipeline: fetch -> clean -> chunk -> embed -> summarize -> store
- [x] ChromaDB vector store with chunk-to-document aggregation
- [x] FastAPI `/ingest`, `/recommend`, `/health` endpoints
- [x] API key authentication
- [x] Rate limiting (10/min ingest, 60/min recommend, keyed by API key)
- [x] Fix race condition on concurrent ingestion of the same URL
- [x] Fix `.env` loading and silent summarizer failures
- [x] Fix chunk-scan crowding-out bug (large docs hiding small relevant ones)

## In progress / next up

- [ ] **Profession- and capability-aware recommendations.** Currently pure
      vector similarity between profile text and content — matches topic,
      not reading level or role-relevance. Needs an architecture decision
      before implementation:
      - Query-time approach: an LLM call interprets the profile's actual
        needs before searching (higher latency/cost per query, no ingest
        changes needed).
      - Ingest-time approach: tag each document with metadata (difficulty,
        relevant professions) when it's added; query time just filters/matches
        against tags (cheaper per query, requires re-tagging existing content).
      - Hybrid: broad retrieval by topic similarity first, then an LLM
        re-ranks the candidates specifically for the stated profession.
      Decision not yet made — see conversation/design notes before starting.

## Backlog — infrastructure

- [ ] ChromaDB is a single local file — no backup, no multi-instance
      deployment story. Needed before any real multi-user or production use.
- [ ] Request coalescing for concurrent ingestion of the same URL (current
      lock fixes correctness but still wastes a duplicate Claude API call
      when two requests race for the same URL — see `DESIGN.md`).
- [ ] Per-user API keys instead of one shared static key, if the API is
      ever used by more than one consumer (current rate limit budget is
      shared globally across anyone with the key).
- [ ] Load testing — nothing in `PERFORMANCE.md` has been measured under
      real concurrent traffic, only a 5-thread test for the locking fix.

## Backlog — content quality

- [ ] YouTube video titles aren't fetched (would need a separate YouTube
      Data API key) — video ID is used as a placeholder title.
- [ ] No retry logic on failed URL fetches (dead link on first try =
      permanent failure for that ingest call, no automatic retry).
- [ ] No content deduplication beyond exact-URL matching — the same article
      reachable via two different URLs (e.g. with/without tracking params)
      would be indexed twice.
- [ ] No handling for paywalled or JS-rendered pages beyond reporting them
      as extraction failures.

## Backlog — nice to have, not urgent

- [ ] Proper structured logging instead of `print()` for warnings (fine for
      a laptop, not fine once this runs somewhere with real log aggregation).
- [ ] `/health` endpoint could report more (embedding model status, last
      successful ingest time) if this ever needs real monitoring.
- [ ] Formal content taxonomy (topic categories, difficulty tiers) if the
      profession-aware ranking work above ends up needing structured tags
      rather than free-text LLM reasoning at query time.
