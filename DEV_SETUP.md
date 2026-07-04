# Dev Setup

## Contents

- [Prerequisites](#prerequisites)
- [1. Clone and enter the repo](#1-clone-and-enter-the-repo)
- [2. Create and activate a virtual environment](#2-create-and-activate-a-virtual-environment)
- [3. Install dependencies](#3-install-dependencies)
- [4. Set up your secrets](#4-set-up-your-secrets)
- [5. Run the test suite](#5-run-the-test-suite)
- [6. Run the server](#6-run-the-server)
- [7. Try it for real](#7-try-it-for-real)
- [If something breaks](#if-something-breaks)
- [Backing up your data](#backing-up-your-data)

## Prerequisites

- Python 3.11+ (developed and tested on 3.14 — see
  [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you're on a very new Python
  version and hit dependency install issues)
- An Anthropic API key (for summarization) — get one at console.anthropic.com
- macOS/Linux commands below; on Windows, adjust activation commands as noted

## 1. Clone and enter the repo

```bash
git clone <this repo's URL>
cd content-curator
```

## 2. Create and activate a virtual environment

This keeps this project's packages isolated from every other Python project
on your machine — necessary, not optional, especially on modern macOS which
actively blocks global installs.

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate          # Windows
```

You'll know it worked if your terminal prompt now starts with `(venv)`.
**You must run the `source` command again in every new terminal window** you
open to work on this project — it doesn't stay active automatically.

## 3. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

If this fails, it's very likely a dependency/Python-version compatibility
issue that's already been hit and documented — check
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) before troubleshooting from
scratch.

## 4. Set up your secrets

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill in two separate values:

```
ANTHROPIC_API_KEY=sk-ant-...
CURATOR_API_KEY=<generate this yourself, see below>
```

`ANTHROPIC_API_KEY` is what this server uses to call Claude for
summarization — get it from your Anthropic console account.

`CURATOR_API_KEY` is invented by you — it's what callers of *this* API must
present. Generate a strong random one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output into `.env`. Never commit `.env` itself — it's already in
`.gitignore`.

## 5. Run the test suite

```bash
PYTHONPATH=src python3 tests/test_vectorstore.py
PYTHONPATH=src python3 tests/test_pipeline.py
PYTHONPATH=src python3 tests/test_main.py
```

Each should print `ALL TESTS PASSED`. These tests don't need your API keys
or internet access — they mock external dependencies (see
[CONTRIBUTING.md](CONTRIBUTING.md) for why).

## 6. Run the server

```bash
python3 -m uvicorn main:app --reload --app-dir src
```

First request will pause briefly while the local embedding model downloads
(~80MB, one-time, cached after that). Leave this running in its own
terminal.

## 7. Try it for real

Open a second terminal. Confirm the server's alive (no auth needed):

```bash
curl http://localhost:8000/health
```

Ingest something (replace `YOUR_KEY` with your real `CURATOR_API_KEY`):

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"urls": ["https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)"]}'
```

Ask for a recommendation:

```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"profile": "VP of Engineering who needs to understand LLMs in 30 minutes", "top_n": 5}'
```

You should get back ranked results with real AI-generated summaries. If you
do, your local setup is fully working end to end.

Also worth browsing: `http://localhost:8000/docs` — FastAPI's
auto-generated interactive API documentation, useful for exploring the
request/response shapes without writing `curl` commands by hand.

## If something breaks

Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first — most issues hit
during this project's own development are documented there with the actual
fix, not a generic suggestion.

## Backing up your data

`chroma_data/` is your entire index — every ingested document and its
embeddings live there, and there's currently no automatic durability beyond
whatever's on your disk (see `TODO.md`/`DESIGN.md` for the bigger
infrastructure options this project deliberately isn't using yet).

Run a backup manually anytime:

```bash
./scripts/backup_chroma.sh
```

By default this writes timestamped zip files to `~/content-curator-backups`
and automatically keeps only the most recent 14, deleting older ones.

**Point it somewhere that actually survives a disk failure**, not just a
different folder on the same disk — a Dropbox/Google Drive/iCloud Drive
folder is the easiest way to get real off-machine protection without
setting up anything new:

```bash
BACKUP_DIR=~/Dropbox/content-curator-backups ./scripts/backup_chroma.sh
```

**Restoring** from a backup (this safely moves your current `chroma_data/`
aside first, rather than deleting it, in case the restore isn't what you
wanted):

```bash
./scripts/restore_chroma.sh ~/content-curator-backups/chroma_data_backup_2026-07-04_10-30-00.zip
```

**Automating it on macOS:** the obvious move is a cron job, but macOS's
cron has a real, common gotcha — it often lacks the permissions
(Full Disk Access) needed to actually run reliably, and fails silently. A
`launchd` user agent is the more reliable native alternative on macOS, if
you want this fully automatic rather than a manual habit. Not set up by
default in this project — a manual `./scripts/backup_chroma.sh` before
anything risky (a big ingest run, an upgrade, cleaning old data) is a
reasonable habit until/unless you set up real scheduling.
