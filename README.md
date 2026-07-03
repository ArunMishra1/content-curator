# AI Content Curator

## Contents

- [What this does](#what-this-does)
- [Status](#status)
- [Quick start](#quick-start)
- [Architecture at a glance](#architecture-at-a-glance)
- [API](#api)
- [Documentation index](#documentation-index)
- [License](#license)

## What this does

Given a list of URLs (articles or YouTube videos), ingest and index their
content. Given a reader profile (e.g. "VP of Engineering who needs to
understand LLMs in 30 minutes"), return the top ranked pieces of content
with an AI-generated summary of each.

## Status

Working MVP with real authentication, rate limiting, and concurrency
safety — not a toy demo, but also not yet production-hardened. No
multi-user account system, single-node local vector store, never
load-tested. See [TODO.md](TODO.md) for the honest list of what's still
missing before this could serve real, multiple users.

## Quick start

Full walkthrough in [DEV_SETUP.md](DEV_SETUP.md). Short version:

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY and CURATOR_API_KEY
python3 -m uvicorn main:app --reload --app-dir src
```

## Architecture at a glance

```
URL --> extractor (web or YouTube) --> chunker --> embedder --> ChromaDB
                                          |
                                      summarizer (once, at ingest time)
```

Full breakdown of every module in [ARCHITECTURE.md](ARCHITECTURE.md).

## API

Two authenticated endpoints (`X-API-Key` header required), plus a public
health check:

- `POST /ingest` — add one or more URLs to the index
- `POST /recommend` — get ranked recommendations for a reader profile
- `GET /health` — liveness check, no auth required

Full request/response shapes are in `src/main.py`'s Pydantic models, or via the
auto-generated docs at `http://localhost:8000/docs` once the server is running.

## Documentation index

| Doc | What's in it |
|---|---|
| [DEV_SETUP.md](DEV_SETUP.md) | Full local setup, running the server, running tests |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System structure — what each module does and how data flows through it |
| [DESIGN.md](DESIGN.md) | *Why* things are built the way they are — the reasoning behind every non-obvious choice |
| [TAXONOMY.md](TAXONOMY.md) | What the product can currently do, what's planned, and how to add a new content-source pattern |
| [CHANGELOG.md](CHANGELOG.md) | Chronological history of what was built and fixed, and when |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Every real bug hit during development and its actual fix |
| [PERFORMANCE.md](PERFORMANCE.md) | Known performance characteristics — and an honest list of what's never been measured |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev conventions, testing philosophy, PR expectations |
| [SKILLS.md](SKILLS.md) | Tech stack and techniques used, with reasoning |
| [TODO.md](TODO.md) | Roadmap — done, in progress, and backlog |
| [CLAUDE.md](CLAUDE.md) | Context file for AI-assisted work on this repo |

## License

Apache 2.0 — see [LICENSE](LICENSE).
