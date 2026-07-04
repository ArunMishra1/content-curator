# Troubleshooting

## Contents

- [pip: command not found](#pip-command-not-found)
- [error: externally-managed-environment](#error-externally-managed-environment)
- [ModuleNotFoundError: No module named 'chromadb' (or any dependency)](#modulenotfounderror-no-module-named-chromadb-or-any-dependency)
- [youtube-transcript-api version not found / won't install](#youtube-transcript-api-version-not-found--wont-install)
- [pydantic-core fails to build from source (Rust/maturin/PyO3 errors)](#pydantic-core-fails-to-build-from-source-rustmaturinpyo3-errors)
- [General pattern: dependency fails to install on a very new Python version](#general-pattern-dependency-fails-to-install-on-a-very-new-python-version)
- [A file you replaced still shows old behavior after "fixing" it](#a-file-you-replaced-still-shows-old-behavior-after-fixing-it)
- [Pasting multi-line code into Terminal corrupts it](#pasting-multi-line-code-into-terminal-corrupts-it)
- [Summaries are empty / silently missing](#summaries-are-empty--silently-missing)
- [Failed to send telemetry event...](#failed-to-send-telemetry-event-capture-takes-1-positional-argument-but-3-were-given)
- [Number of requested results N is greater than number of elements in index M](#number-of-requested-results-n-is-greater-than-number-of-elements-in-index-m)
- [401 Unauthorized on /ingest or /recommend](#401-unauthorized-on-ingest-or-recommend)
- [429 Too Many Requests](#429-too-many-requests)

Every issue below actually happened during development of this project, in
this exact environment (macOS, Python 3.14). Listed in case you hit the same
thing.

---

### `pip: command not found`

Use `python3 -m pip` instead of bare `pip`. On some Mac setups `pip` isn't
on the PATH even when Python is installed correctly.

---

### `error: externally-managed-environment`

Modern macOS Python (via Homebrew) refuses global `pip install` to protect
the system Python installation. Fix: use a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

You must run `source venv/bin/activate` in every new terminal session
before working on this project, or you'll get `ModuleNotFoundError` even
though you already installed everything (you'd be back on system Python).

---

### `ModuleNotFoundError: No module named 'chromadb'` (or any dependency)

You haven't installed requirements yet, or you're not in the activated
virtual environment. Run:
```bash
python3 -m pip install -r requirements.txt
```

---

### `youtube-transcript-api` version not found / won't install

The version originally pinned in `requirements.txt` (`0.6.3`) doesn't
support Python 3.14. Fixed by pinning `1.2.4` instead — but if you're
reading this because it broke again, the library's API changed between
major versions (`0.x` used a static `get_transcript()` method; `1.x` uses
an instance method `.fetch()`). Check `src/extractors/youtube.py` matches
whatever version actually installed:
```bash
pip show youtube-transcript-api
```

---

### `pydantic-core` fails to build from source (Rust/maturin/PyO3 errors)

Happens when the pinned `pydantic` version predates your Python version and
no prebuilt wheel exists, forcing a from-source build that the Rust
tooling (PyO3) doesn't yet support for that Python version. Fix: use a
newer `pydantic` version that has a prebuilt wheel for your Python version.
Check what's available:
```bash
curl -s https://pypi.org/pypi/pydantic-core/json | python3 -c "
import json, sys
data = json.load(sys.stdin)
latest = data['info']['version']
files = data['releases'][latest]
print([f['filename'] for f in files if 'YOUR_PYTHON_VERSION_TAG' in f['filename']])
"
```

---

### General pattern: dependency fails to install on a very new Python version

If you're on a Python version released within the last ~12 months, expect
some dependencies — especially ones with compiled/Rust/C internals — to lag
behind with prebuilt wheels. This isn't a bug in this project or in Python;
it's a normal ecosystem-catch-up lag after every major Python release. Two
options: patch pins as you hit them (what this project has done so far), or
use an older, more established Python version (3.11/3.12) for less friction.

---

### A file you replaced still shows old behavior after "fixing" it

Check the actual filename case:
```bash
ls -la path/to/the/file.py
```

macOS's default filesystem (APFS) is case-insensitive but case-preserving —
`Youtube.py` and `youtube.py` look identical to `ls`, `cat`, and `grep`, but
Python's import system does an exact case check and will silently fail to
find the "same" file if the case doesn't match exactly
(`ModuleNotFoundError` or `ImportError`, depending on how it's imported).
This actually happened during development — a downloaded file replacement
landed as `Youtube.py` and every verification command *except the actual
Python import* showed it as correct.

Fix: rename explicitly (a direct same-name rename can no-op on a
case-insensitive filesystem, so go through a temp name):
```bash
mv src/extractors/Youtube.py src/extractors/youtube_temp.py
mv src/extractors/youtube_temp.py src/extractors/youtube.py
```
Then clear stale bytecode cache, which can also mask the fix:
```bash
rm -rf src/extractors/__pycache__ __pycache__
```

---

### Pasting multi-line code into Terminal corrupts it

Some terminal setups (autosuggestion plugins, smart-quote substitution,
long-line handling) corrupt large multi-line pastes — symptoms include
duplicated fragments, mangled quotes, or URLs turned into markdown links.
If this happens: don't fight it. Use Finder to drag-and-drop the actual
file instead of pasting code into the terminal at all.

---

### Summaries are empty / silently missing

Check that `ANTHROPIC_API_KEY` is actually loaded:
```bash
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(bool(os.environ.get('ANTHROPIC_API_KEY')))"
```
If this prints `False`, your `.env` file either doesn't exist, isn't in the
directory you're running from, or doesn't have the key set. Note: creating
a `.env` file does nothing by itself — something has to load it
(`python-dotenv`'s `load_dotenv()`, already wired into `src/summarizer.py` and
`src/auth.py`). If you ever see a summary silently come back empty, check the
terminal running `uvicorn` for a `[WARNING] Summary generation failed...`
line — this failure is intentionally never swallowed silently.

---

### `Failed to send telemetry event... capture() takes 1 positional argument but 3 were given`

Harmless. Version mismatch between ChromaDB's internal analytics call and
the `posthog` library it uses. Doesn't affect functionality or your data.
Safe to ignore.

---

### `Number of requested results N is greater than number of elements in index M`

Informational, not an error. ChromaDB is telling you it was asked for more
candidate matches than currently exist in the index — it just returns what
it has. Expected with a small/new index; will stop appearing as more
content is ingested.

---

### 401 Unauthorized on `/ingest` or `/recommend`

You're missing the `X-API-Key` header, or the value doesn't match
`CURATOR_API_KEY` in your `.env`. Check what's actually set:
```bash
cat .env
```
Note: `ANTHROPIC_API_KEY` and `CURATOR_API_KEY` are two different keys for
two different purposes — see `README.md` if you're mixing them up.

---

### 429 Too Many Requests

Working as intended — you've hit the rate limit (10/min on `/ingest`,
20/min on `/recommend`). Wait a minute, or see `DESIGN.md` for why the
limit is shared across all callers of a single API key.
