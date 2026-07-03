"""
API key authentication for the ingest and recommend endpoints.

Design: a single static key, checked via a request header (X-API-Key), not
a full user-account/JWT system. Why this is the right call right now: you
have exactly one trust boundary today -- "callers who have the key" vs
"the public internet" -- not multiple users needing different permissions.
Building JWT/OAuth2 infrastructure for a permission model you don't have yet
is complexity with no current payoff. This is also a contained decision:
if you later need per-user keys or roles, only this file changes -- the
endpoints just depend on "verify_api_key," not on how verification works.

The key itself lives in .env (CURATOR_API_KEY), loaded the same way
ANTHROPIC_API_KEY is -- via python-dotenv, so it's never committed to git.
"""

import os
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(provided_key: str = Security(_api_key_header)) -> str:
    expected_key = os.environ.get("CURATOR_API_KEY")

    if not expected_key:
        # Fail loud, not open. If the server operator forgot to set a key,
        # that's a deployment mistake -- the correct behavior is "nobody can
        # use the API" (safe), not "auth is silently disabled" (dangerous).
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: CURATOR_API_KEY is not set."
        )

    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header."
        )

    # secrets.compare_digest instead of `==`: a plain string comparison
    # exits early on the first mismatched character, which means the time
    # it takes to reject a guess leaks how many leading characters were
    # correct (a "timing attack"). compare_digest always takes the same
    # amount of time regardless of where the mismatch is, so an attacker
    # can't use response speed to guess the key character by character.
    # Overkill for most side projects, but costs nothing to do right here.
    if not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key."
        )

    return provided_key
