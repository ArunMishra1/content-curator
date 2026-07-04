"""
Query-time re-ranking: takes a broad set of topically-similar candidates
(from vector search) and has an LLM reason about which ones actually fit
THIS reader's profession and situation, in what order.

This is a deliberate reversal of the "no LLM at query time" principle
documented in DESIGN.md for the base retrieval flow. That principle still
holds for the vector search step itself -- this module runs AFTER it, as an
additional reasoning pass, not a replacement. Accepted tradeoff: /recommend
is no longer purely cheap/instant. See DESIGN.md for the full reasoning.

Cost controls, deliberate:
- Only short summaries are sent to the LLM, never full document text.
- The candidate pool is capped (see MAX_CANDIDATES) regardless of how many
  the caller's top_n requests, bounding input tokens per call.
- Haiku, not a larger model -- this is a ranking/reasoning task on short
  text, not a task needing maximum capability.
"""

import json
from typing import List, Dict, Any
from anthropic import Anthropic
from dotenv import load_dotenv
import os

load_dotenv()

RERANK_MODEL = "claude-haiku-4-5-20251001"
MAX_CANDIDATES = 20  # hard cap on how many candidates get sent to the LLM, regardless of top_n

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
        _client = Anthropic(api_key=api_key)
    return _client


def _build_prompt(profile: str, candidates: List[Dict[str, Any]], top_n: int) -> str:
    candidate_lines = []
    for c in candidates:
        candidate_lines.append(
            f'- doc_id: {c["doc_id"]} | format: {c["source_type"]} | title: "{c["title"]}" | summary: "{c["summary"]}"'
        )
    candidates_block = "\n".join(candidate_lines)

    return f"""A reader with this profile is looking for content: "{profile}"

Below are {len(candidates)} candidate pieces of content that matched on topic. Your job is to
reason about what someone in THIS specific position actually needs -- their likely
expertise level, their time constraints, what they'd do with this information -- and
select and rank the best fit. Prioritize genuine fit for this reader over superficial
topic overlap. A technically deeper piece is not automatically better; a beginner-level
piece is not automatically worse -- match the reader's actual situation.

Candidates:
{candidates_block}

Respond with ONLY a JSON array, no other text, no markdown code fences. Exact shape:
[{{"doc_id": "...", "reason": "one sentence: why this specifically fits this reader"}}, ...]

Return at most {top_n} items, ordered best-fit first. If fewer than {top_n} candidates
are genuinely a good fit for this reader, return fewer -- do not pad the list with
weak matches just to reach {top_n}."""


def _parse_llm_response(raw_text: str, valid_doc_ids: set) -> List[Dict[str, str]]:
    text = raw_text.strip()
    # Claude sometimes wraps JSON in markdown fences despite instructions not to -- strip them defensively.
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    parsed = json.loads(text)  # let this raise on genuine parse failure -- caller handles it

    results = []
    for item in parsed:
        doc_id = item.get("doc_id")
        # Defensive: never trust an LLM to only return IDs we actually gave it.
        # Silently drop hallucinated IDs rather than surfacing a broken result.
        if doc_id in valid_doc_ids:
            results.append({"doc_id": doc_id, "reason": item.get("reason", "")})
    return results


def rerank_for_profile(profile: str, candidates: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """
    candidates: list of dicts from VectorStore.query() (doc_id, url, title,
    source_type, summary, score, ...).

    Returns candidates re-ordered and trimmed to top_n, each with an added
    "reason" field explaining the fit. Falls back to the original
    vector-similarity order (no "reason" field) if the LLM call fails or
    returns something unparseable -- a broken re-rank should never mean a
    broken /recommend response.
    """
    if not candidates:
        return []

    pool = candidates[:MAX_CANDIDATES]
    valid_ids = {c["doc_id"] for c in pool}
    by_id = {c["doc_id"]: c for c in pool}

    try:
        client = _get_client()
        prompt = _build_prompt(profile, pool, top_n)
        response = client.messages.create(
            model=RERANK_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        ranked = _parse_llm_response(response.content[0].text, valid_ids)

        if not ranked:
            raise ValueError("LLM returned no usable picks after validation")

        output = []
        for item in ranked[:top_n]:
            doc = dict(by_id[item["doc_id"]])
            doc["reason"] = item["reason"]
            output.append(doc)
        return output

    except Exception as e:
        print(f"[WARNING] LLM re-rank failed, falling back to vector-similarity order: {e}")
        fallback = []
        for c in pool[:top_n]:
            doc = dict(c)
            doc["reason"] = ""
            fallback.append(doc)
        return fallback
