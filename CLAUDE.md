# Notes for Claude (or Claude Code) working on this repo

## Contents

- [What this project is](#what-this-project-is)
- [Before making changes](#before-making-changes)
- [Testing requirements for any change](#testing-requirements-for-any-change)
- [Known gaps](#known-gaps--see-todomd-for-the-full-list-but-the-two-biggest)
- [Style conventions](#style-conventions)
- [Secrets](#secrets)

## What this project is

An AI content curator: ingest URLs (articles or YouTube videos), index them,
and return ranked recommendations for a given reader profile with
AI-generated summaries. See `README.md` for the user-facing overview,
`ARCHITECTURE.md` for how it's built, `DESIGN.md` for why.

## Before making changes

1. Read `DESIGN.md` first if the change touches anything architectural —
   several choices that look like they could be "simplified" or "obviously
   improved" were made deliberately with a documented tradeoff (chunk size,
   summarization timing, auth model, locking strategy). Don't undo a
   documented tradeoff without understanding what it was protecting against.
2. Check `TROUBLESHOOTING.md` before assuming a new install/environment
   issue is novel — several Python-3.14-specific dependency issues have
   already been hit and solved here.
3. This project runs on Python 3.14 on macOS. Dependency pins have already
   been adjusted twice for 3.14 wheel availability (`pydantic`,
   `youtube-transcript-api`) — if you change `requirements.txt`, verify the
   new pin actually has a prebuilt wheel for 3.14, not just that it exists
   on PyPI.

## Testing requirements for any change

- Every module has a corresponding test file in `tests/` — extend it, don't
  create a parallel one.
- Tests mock external dependencies (real embedding model, real Anthropic
  API, real network) — see `CONTRIBUTING.md`'s testing philosophy section.
  Don't add a test that requires an API key or internet access to pass.
- If the change is a bug fix, add a regression test, and verify it actually
  fails without your fix before considering it done (see the concurrency
  test and crowding-out test in `tests/` for the pattern — both were
  verified this way).
- Run the full suite before considering any change complete:
  ```bash
  PYTHONPATH=src python3 tests/test_vectorstore.py
  PYTHONPATH=src python3 tests/test_pipeline.py
  PYTHONPATH=src python3 tests/test_main.py
  ```

## Known gaps — see TODO.md for the full list, but the two biggest:

1. **ChromaDB is a single local file** — no backup, no multi-instance
   deployment story. The real gap before any production/multi-user use.
2. **Re-ranking results aren't cached.** Every `/recommend` call triggers a
   fresh LLM call in `src/ranker.py`, even for an identical profile
   searched moments ago. Not urgent at current traffic, but a real cost
   optimization opportunity if usage grows.

(Resolved: profession/difficulty-aware ranking, previously listed here as
the top gap, was built via query-time LLM re-ranking — see `DESIGN.md` and
`src/ranker.py`.)

## Style conventions

- Type hints on all function signatures.
- Docstrings/comments explain *why*, not *what* — don't add a comment that
  just restates the code in English.
- Dataclasses for shared data shapes (`src/models.py`), not ad-hoc dicts passed
  between modules.
- Silent failure is not acceptable — anything that can fail either raises
  or logs visibly (see the `.env`-loading bug in `CHANGELOG.md` for why
  this rule exists: a silently swallowed exception hid a real bug for
  multiple testing sessions).

## Secrets

Two separate keys, easy to confuse: `ANTHROPIC_API_KEY` (this server calling
Claude) and `CURATOR_API_KEY` (callers calling this server). Both live in
`.env` (gitignored), never in code, never hardcoded, never logged.
