# Contributing

## Contents

- [Setup](#setup)
- [Running tests](#running-tests)
- [Testing philosophy — read this before adding a test](#testing-philosophy--read-this-before-adding-a-test)
- [Code conventions](#code-conventions)
- [Commit messages](#commit-messages)
- [Before opening a PR](#before-opening-a-pr)

## Setup

```bash
git clone <this repo>
cd content-curator
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and CURATOR_API_KEY in .env
```

If `pip install` fails on a dependency, check `TROUBLESHOOTING.md` first —
several real version-incompatibility issues have already been hit and fixed
(Python 3.14 compatibility problems, mainly), and the fix or workaround is
probably already documented there.

## Running tests

Every module has a corresponding test file in `tests/` that runs standalone:

```bash
PYTHONPATH=. python3 tests/test_vectorstore.py
PYTHONPATH=. python3 tests/test_pipeline.py
PYTHONPATH=. python3 tests/test_main.py
```

Each should print `ALL TESTS PASSED`.

## Testing philosophy — read this before adding a test

Tests in this project deliberately **mock external dependencies** (the real
embedding model, the Anthropic API, real network fetches) rather than
requiring them. Reasons:

- Tests should run in milliseconds, anywhere, without an API key or internet
  access.
- A test should verify *our* logic, not re-verify that a well-established
  library (ChromaDB, sentence-transformers) does what its own test suite
  already proves it does.

When you add a test for new logic, ask: am I testing code we wrote, or
re-testing a dependency? If the latter, you probably don't need the test.

**A test that can't fail isn't a test.** Before trusting a test that
verifies a fix (a bug fix, a security control, a race condition guard),
deliberately break the fix and confirm the test actually catches it. This
project's concurrency test and vector-store crowding-out test were both
verified this way — see their code comments for the sabotage method used.

## Code conventions

- Type hints on function signatures.
- Docstrings explain **why**, not just what — a comment restating the code
  in English is not useful; a comment explaining the tradeoff or reasoning
  behind a non-obvious choice is.
- Dataclasses (`models.py`) for shared data shapes — no ad-hoc dicts passed
  between modules with implicit field names.
- Silent failure is treated as a bug. If something can fail, either handle
  it explicitly and visibly (a warning, a logged error) or let it raise.
  The `.env`-loading bug documented in `CHANGELOG.md` existed specifically
  because a failure was swallowed without a trace.

## Commit messages

Describe what changed and why, not just what file was touched. Look at
`CHANGELOG.md` or `git log` for the established style — generally: a short
summary line, then bullet points for anything non-obvious about the reasoning.

## Before opening a PR

1. Run the full test suite (all three files above).
2. If you touched `requirements.txt`, note in your PR description which
   Python version you tested against — this project has already been bitten
   twice by version-specific wheel availability (see `TROUBLESHOOTING.md`).
3. If you're fixing a bug, add a test that would have caught it, and confirm
   the test actually fails without your fix (see testing philosophy above).
