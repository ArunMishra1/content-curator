<!--
Thanks for contributing. Fill in what's relevant, delete what isn't.
See CONTRIBUTING.md for the full expectations behind this checklist.
-->

## What does this change?

<!-- One or two sentences: what changed, and why. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation only
- [ ] Refactor (no behavior change)
- [ ] Dependency/version update

## Testing performed

<!--
How did you verify this works? "I ran the test suite" is a minimum,
not a complete answer -- what did you check manually, and against what?
-->

- [ ] Ran the full test suite (`tests/test_vectorstore.py`, `tests/test_pipeline.py`, `tests/test_main.py`) — all passing
- [ ] Added a new test covering this change
- [ ] If this is a bug fix: confirmed the new test actually fails without the fix (see CONTRIBUTING.md's testing philosophy — a test that can't fail isn't a test)
- [ ] Tested manually against a running server (`uvicorn main:app --reload --app-dir src`), not just unit tests

## If you touched `requirements.txt`

- [ ] Noted which Python version you tested the install against (this project has hit real wheel-availability issues on very new Python versions — see TROUBLESHOOTING.md)

## Checklist

- [ ] Docs updated if this changes setup steps, API behavior, or architecture (`README.md`, `DEV_SETUP.md`, `ARCHITECTURE.md`, `TAXONOMY.md` as relevant)
- [ ] `CHANGELOG.md` updated
- [ ] No secrets, API keys, or `.env` contents included in this diff

## Related issues

<!-- Link any related issue/TODO item, e.g. "Addresses item in TODO.md under Backlog — infrastructure" -->
