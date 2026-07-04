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
- [x] Rate limiting (10/min ingest, 20/min recommend, keyed by API key —
      recommend's limit tightened from an initial 60/min once it started
      making a real LLM call)
- [x] Fix race condition on concurrent ingestion of the same URL
- [x] Fix `.env` loading and silent summarizer failures
- [x] Fix chunk-scan crowding-out bug (large docs hiding small relevant ones)
- [x] Profession- and capability-aware recommendations via query-time LLM
      re-ranking (`ranker.py`) — see `DESIGN.md` for why this approach was
      chosen over ingest-time tagging alternatives
- [x] Manual backup/restore scripts for `chroma_data/` (`scripts/backup_chroma.sh`,
      `scripts/restore_chroma.sh`) — protects against accidental deletion
      and disk corruption if pointed at an off-machine destination

## In progress / next up

Nothing currently in progress. Next priorities, in rough order:

- [ ] Load testing (see `PERFORMANCE.md`) — nothing has been measured under
      real concurrent traffic yet

## Backlog — infrastructure

- [ ] ChromaDB multi-instance support (client-server mode, managed vector
      DB, or Postgres+pgvector — see `DESIGN.md` for the full comparison).
      Deliberately deferred: solves a problem this project doesn't have yet
      (running more than one server instance). Revisit when that becomes
      real, not before. Basic data-loss protection is already covered by
      `scripts/backup_chroma.sh`.
- [ ] Request coalescing for concurrent ingestion of the same URL (current
      lock fixes correctness but still wastes a duplicate Claude API call
      when two requests race for the same URL — see `DESIGN.md`).
- [ ] Cache re-ranking results for identical/near-identical profile
      searches — right now every `/recommend` call triggers a fresh LLM
      call even if the exact same profile was searched a minute ago.
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
