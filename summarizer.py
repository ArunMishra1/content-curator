"""
Generates a short summary of a document, once, at ingest time.

Model choice: Claude Haiku, not a bigger model. Summarizing text is a bulk,
repetitive, low-reasoning task — you're doing this once per document, and if
you ingest a few thousand URLs, cost adds up fast with a larger model for no
quality benefit that matters here. Reserve bigger models for tasks that
actually require deep reasoning.

Requires an ANTHROPIC_API_KEY environment variable. This is the one place in
the pipeline where an API key is mandatory (embeddings are local — free —
but there is no good free local option for decent-quality summarization).
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load .env into the environment. Without this, os.environ.get() below never
# sees keys set in a .env file -- only ones exported directly in the shell.
# This was a real gap: .env.example implied .env would "just work," but
# nothing was actually loading it. Loading it here, at the point where the
# key is consumed, means it works regardless of whether the caller is
# main.py (the API server), pipeline.py (direct script use), or a test.
load_dotenv()

SUMMARIZER_MODEL = "claude-haiku-4-5-20251001"

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Summarization requires it — set it with: export ANTHROPIC_API_KEY=your_key"
            )
        _client = Anthropic(api_key=api_key)
    return _client


def summarize(title: str, text: str, max_words: int = 60) -> str:
    """
    Truncate very long documents before sending — no point paying to send
    20,000 words to summarize when the first ~4000 words usually captures
    what the piece is about. This is a cost control, not a quality choice;
    revisit if you find summaries missing key later-document content.
    """
    truncated = text[:16000]

    client = _get_client()
    response = client.messages.create(
        model=SUMMARIZER_MODEL,
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                f"Summarize the following content in {max_words} words or fewer. "
                f"Be specific about what it actually covers — not generic. "
                f"No preamble, just the summary.\n\n"
                f"Title: {title}\n\nContent:\n{truncated}"
            )
        }]
    )
    return response.content[0].text.strip()
