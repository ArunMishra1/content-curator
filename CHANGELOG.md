# Changelog

## Contents

- [2026-07-04 (product cohesion)](#2026-07-04-product-cohesion)
- [2026-07-04 (discovery)](#2026-07-04-discovery)
- [2026-07-04 (frontend)](#2026-07-04-frontend)
- [2026-07-04 (backups)](#2026-07-04-backups)
- [2026-07-03 (ranking)](#2026-07-03-ranking)
- [2026-07-03 (restructure)](#2026-07-03-restructure)
- [2026-07-03](#2026-07-03)
- [2026-07-02 (evening)](#2026-07-02-evening)
- [2026-07-02 (afternoon)](#2026-07-02-afternoon)
- [2026-07-02 (initial)](#2026-07-02-initial)

All notable changes to this project, in the order they actually happened.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## 2026-07-04 (product cohesion)

### Added
- Connected `/recommend` and `/discover` in the frontend: when a search
  returns zero results, the UI now shows a "Search the web for this" button
  instead of a dead-end message. Clicking it opens the ingest panel,
  pre-fills the discovery query with the reader profile, and runs the same
  discovery flow already built — no new backend endpoint needed, purely
  frontend wiring between two features that already existed independently.
- Deliberate prioritization call: chose this over several smaller polish
  items (YouTube title fetching, URL deduplication, retry logic) because it
  changes what the product *does* rather than making an existing feature
  slightly more correct — the difference between two features that happen
  to coexist and one product that holds together.
- Verified via headless browser: empty-result state renders the CTA,
  clicking it correctly pre-fills the discovery query with the exact
  profile text, opens the ingest section, and surfaces real candidates —
  and a precise bounding-box check (not just a screenshot glance) confirmed
  no layout overlap between the message and button.

## 2026-07-04 (discovery)

### Added
- `src/discover.py` and `POST /discover`: finds candidate URLs for a topic
  via the Tavily search API. Deliberately does NOT auto-ingest results —
  see `DESIGN.md` for why (ingestion costs a real Claude call per document;
  auto-ingesting search results risks spending that on junk).
- Frontend: discovery UI inside the existing "Add content" panel — search
  a topic, get checkboxes of candidates with title/snippet, selected ones
  get added to the same reviewable URL textarea the manual-entry flow
  already used. No new ingestion code path in the frontend; the existing
  "Ingest" button is what actually does anything.
- `tests/test_discover.py`: 5 tests, all mocking the Tavily client (no real
  API call needed to run).
- 5 new tests in `test_main.py` covering the `/discover` endpoint: auth
  enforcement, response shaping, validation, and clean error handling for
  both a missing `TAVILY_API_KEY` (500) and a genuine Tavily API failure (502).

### Considered and rejected
- Building an actual web crawler instead of using a search API — evaluated
  seriously (robots.txt/politeness, JS-rendered pages, bot detection,
  crawler traps, relevance-ranking-at-scale, and real unsettled legal
  exposure around automated scraping), and rejected as solving a much
  bigger problem than this project actually has. Full reasoning in `DESIGN.md`.
- Bing Search API — fully retired August 2025, not usable at all.
- Google Custom Search JSON API — closed to new signups since 2025,
  sunsetting entirely by 2027. Not usable for a new integration.
- Brave Search API — real and viable, but dropped its free tier in
  February 2026 (now requires a credit card for any use). Logged as the
  fallback option if Tavily's free tier or quality isn't sufficient.

## 2026-07-04 (frontend)

### Added
- `frontend/` — minimal Next.js web UI. Search by reader profile, view
  ranked results with fit explanations (the `reason` field from
  `ranker.py`), collapsible section to add new URLs to the index.
- Server-side proxy pattern (`app/api/recommend/route.js`,
  `app/api/ingest/route.js`, `app/api/health/route.js`): the browser never
  holds `CURATOR_API_KEY` — Next.js server routes hold it and forward
  requests to the FastAPI backend. Chosen over the simpler "paste the key
  into the browser" approach specifically to avoid exposing it in client-
  side network requests.
- Design carries the logo's visual language into the product: same amber/
  navy palette, and ranked results get a colored left-border whose weight
  signals rank (amber for the top match, gray for the rest) — echoing the
  logo's ranked-bars motif.
- Verified: production build succeeds; visually confirmed via headless
  browser screenshots against a mock backend (background color exact match
  to design tokens, amber accent renders in expected locations, computed
  CSS confirms correct per-rank border colors — not just eyeballed);
  ingest toggle, submission, and per-URL success/failure states all
  function correctly; responsive behavior confirmed at mobile viewport width.

### Fixed
- Initial `next` install (14.2.5) carried a disclosed critical
  vulnerability (part of the CVE-2025-55183/55184/67779/66478 family
  affecting React Server Components, one rated CVSS 10.0 for RCE). Pinned
  to `14.2.35`, the patched release for the 14.x line, before building
  anything on top of it.

### Noted, not solved here
- Deploying only the frontend (e.g. to Vercel) does not make the backend
  reachable — `localhost` on your laptop is not reachable from a public
  deployment. Backend hosting remains a separate, not-yet-done step (see
  `TODO.md`).

## 2026-07-04 (backups)

### Added
- `scripts/backup_chroma.sh` and `scripts/restore_chroma.sh` — manual
  backup/restore for `chroma_data/`, with automatic retention (keeps last
  14 backups by default) and a safety copy on restore (never silently
  overwrites existing data). Warns explicitly if configured to back up to
  a location on the same disk as the original, which defeats the point.
- Documented in `DEV_SETUP.md`'s new "Backing up your data" section,
  including the macOS `cron`-permissions gotcha for anyone automating it.

### Changed
- Considered and deferred three bigger infrastructure options (ChromaDB
  client-server mode, managed vector DB, Postgres+pgvector) in favor of
  this — see `DESIGN.md` for the full comparison and why. Logged as a
  deliberately-deferred backlog item in `TODO.md`, not dropped.

## 2026-07-03 (ranking)

### Added
- `src/ranker.py`: query-time LLM re-ranking. `/recommend` now retrieves a
  broad candidate pool by vector similarity (unchanged), then a Claude
  Haiku call reasons about which candidates fit the specific reader's
  profession, expertise level, and time constraints, reordering and
  trimming the results. Each result now includes a `reason` field
  explaining the fit. Falls back to plain vector-similarity order if the
  LLM call fails or returns unparseable output — never a broken response.
- `tests/test_ranker.py`: covers reordering, hallucinated-ID filtering,
  graceful fallback on API failure and on bad output, correct behavior
  when fewer than `top_n` candidates are genuinely a good fit, and the
  candidate-pool cost cap.

### Changed
- Considered and rejected two alternative approaches (ingest-time tagging
  with query-time filtering; a fully embedding-based hybrid with no
  query-time LLM call at all) in favor of this one — see `DESIGN.md` for
  the full reasoning and tradeoffs of all three.
- `/recommend`'s rate limit tightened from 60/minute to 20/minute, since
  this endpoint now makes a real LLM call per request instead of a pure
  vector lookup.
- This reverses part of the "no LLM at query time" principle stated
  elsewhere in `DESIGN.md` for the base retrieval flow — documented
  explicitly there rather than silently contradicted.

## 2026-07-03 (restructure)

### Changed
- All Python source files moved from the repo root into `src/` (including
  the `extractors/` subpackage), matching the existing `tests/` convention.
  Import statements inside the code were deliberately left unchanged — the
  move is handled via `PYTHONPATH=src` (tests) and `--app-dir src`
  (uvicorn), not by converting to a formally packaged project. Verified
  `.env` loading and the `chroma_data/` relative path both still resolve to
  the repo root correctly under this approach (confirmed by test before
  committing to it, not assumed).
- Added `.github/PULL_REQUEST_TEMPLATE.md`.
- Note: file path references below this point in the changelog describe
  where files were *at the time each entry was written* — e.g. "`pipeline.py`"
  in earlier entries correctly refers to the repo root, not `src/pipeline.py`,
  since that's where it actually was when that entry happened. Not
  retroactively rewritten, to keep this file historically accurate.

## 2026-07-03

### Added
- Race condition fix: per-`doc_id` lock in `pipeline.py` serializes concurrent
  ingestion of the same URL, preventing corrupted/interleaved writes to the
  vector store. Verified with a test that sabotages the lock to confirm the
  test actually catches the bug when the fix is absent.
- Rate limiting via `slowapi`: 10 requests/minute on `/ingest` (real Claude
  API cost per call), 60/minute on `/recommend` (cheap, no LLM call). Keyed
  by API key, not IP address.
- API key authentication (`auth.py`) on `/ingest` and `/recommend`, using a
  single static key checked via the `X-API-Key` header with a timing-safe
  comparison. `/health` intentionally left public.
- `main.py`: FastAPI application with `/ingest`, `/recommend`, `/health`
  endpoints. Embedding model loads at server startup, not per-request.

### Fixed
- `.env` file was never actually being loaded into the process — added
  `python-dotenv` and `load_dotenv()` to `summarizer.py`. This had been
  silently causing every summary to fail since the very first pipeline test;
  the failure was invisible because it was swallowed without logging.
- Summarizer failures now print a visible `[WARNING]` instead of failing
  silently — the exact gap that hid the `.env` bug above.
- Vector store's chunk-scan window (`chunks_to_scan`) now scales with index
  size instead of a fixed 30 — previously a large document could crowd out
  a smaller, relevant document's chunks entirely from consideration.

## 2026-07-02 (evening)

### Added
- `pipeline.py`: orchestrates the full ingest flow (extract -> chunk ->
  summarize -> store). Deterministic `doc_id` via SHA-256 hash of the URL.
  Batch ingestion (`ingest_urls`) isolates per-URL failures.
- `tests/test_pipeline.py`: orchestration logic tested via mocks, no network
  or real API calls required.

### Fixed
- `youtube-transcript-api` pinned version (`0.6.3`) didn't support Python
  3.14; upgraded to `1.2.4`, which required rewriting `extractors/youtube.py`
  against the new instance-based API (`.fetch()` instead of the old static
  `.get_transcript()`).
- `pydantic` pinned version (`2.9.2`) had no prebuilt wheel for Python 3.14
  on macOS ARM, causing a Rust compilation failure; unpinned to `>=2.10.0`.
- Case-sensitivity bug: a file replacement briefly left `extractors/Youtube.py`
  (capital Y) instead of `youtube.py` — invisible to `ls`/`cat`/`grep` on
  macOS's case-insensitive filesystem, but Python's import system correctly
  rejected the mismatch. Root-caused and fixed.

## 2026-07-02 (afternoon)

### Added
- `vectorstore.py`: ChromaDB wrapper. Stores at chunk granularity, collapses
  results back to document granularity by keeping each document's
  best-scoring chunk. `upsert` semantics so re-ingesting a URL updates in
  place rather than duplicating.
- `tests/test_vectorstore.py`: uses a deterministic fake embedder (not the
  real model) so the test is fast and has no external dependencies.

## 2026-07-02 (initial)

### Added
- Project scaffold: `embeddings.py` (`EmbeddingProvider` abstraction, local
  sentence-transformers implementation), `models.py` (shared data classes),
  `extractors/web.py` (trafilatura-based article extraction),
  `extractors/youtube.py` (transcript extraction), `chunking.py`
  (overlapping ~500-char chunks), `summarizer.py` (Claude Haiku, once per
  document at ingest time).
- Git repository initialized, Apache 2.0 license added, made public.
