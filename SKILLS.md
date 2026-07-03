# Tech Stack & Techniques

## Contents

- [Core stack](#core-stack)
- [Techniques used](#techniques-used)
- [Environment-specific lessons (macOS + Python 3.14)](#environment-specific-lessons-macos--python-314)

A reference of what this project actually uses and why — useful for
onboarding, for a portfolio summary, or just for remembering what's under
the hood six months from now.

## Core stack

| Area | Technology | Why this one |
|---|---|---|
| API framework | FastAPI | Async-capable, automatic request validation via Pydantic, automatic OpenAPI docs |
| Vector database | ChromaDB | Simple local persistence, no separate server process to run for an MVP |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Free, local, no API key, good enough quality to prove retrieval works |
| Summarization | Anthropic Claude (Haiku model) | Cheap, fast, sufficient for bulk low-reasoning summarization |
| Web content extraction | trafilatura | Purpose-built for stripping boilerplate (nav/ads/comments) from articles, not a generic HTML parser |
| YouTube transcripts | youtube-transcript-api | Direct caption access without needing the full YouTube Data API |
| Rate limiting | slowapi | FastAPI/Starlette-native, avoids hand-rolling counters |
| Config/secrets | python-dotenv | Loads `.env` into the process; keeps secrets out of git |
| Auth | Custom (FastAPI `Security` + `APIKeyHeader`) | Single static key is sufficient for current trust model; see `DESIGN.md` |

## Techniques used

- **Abstract base classes for swappable backends** (`EmbeddingProvider` in
  `embeddings.py`) — define a contract once, write implementations against
  it, swap implementations without touching callers.
- **Dependency injection via FastAPI's `Depends`** — auth and (implicitly)
  the rate limiter are wired in as dependencies, not hardcoded into each
  endpoint body.
- **Deterministic ID generation** (SHA-256 hash of URL) to make storage
  upserts idempotent — same input always maps to the same record.
- **Per-resource locking** (`threading.Lock` per `doc_id`) to make
  concurrent access to a shared resource (the vector store) safe without
  locking the entire system on every write.
- **Chunk-then-aggregate retrieval pattern** — search at fine granularity
  (chunks) for embedding precision, then collapse results to coarse
  granularity (documents) for the user-facing answer.
- **Test doubles over real dependencies** — fake embedders, mocked API
  clients, and a local HTTP test server used throughout so the test suite
  runs without network access, API keys, or GPU/ML dependencies.
- **Sabotage testing** — for tests verifying a fix (the concurrency lock,
  the crowding-out fix), the fix was deliberately disabled once to confirm
  the test actually fails without it, not just passes regardless.

## Environment-specific lessons (macOS + Python 3.14)

Documented in full in `TROUBLESHOOTING.md`, but worth knowing this stack
touches:
- Virtual environment management (`venv`) as a requirement, not an option,
  due to macOS's externally-managed-environment protection.
- Dependency version pinning tradeoffs — exact pins (`==`) are more
  reproducible but break more easily on very new Python versions; range
  pins (`>=`) are more resilient but less reproducible.
- macOS filesystem case-insensitivity vs. Python's case-sensitive import
  system as a real source of "it should work" bugs.
