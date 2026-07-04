"""
Discovers candidate URLs for a topic via the Tavily search API, WITHOUT
ingesting them. This is deliberately a separate step from ingestion: each
ingested document costs a real Claude summarization call, so auto-ingesting
whatever a search API returns risks spending that cost on irrelevant
results. Discovery is cheap (one search call); ingestion of the results
the caller actually wants stays an explicit, separate call to the existing
/ingest endpoint -- unchanged, no new code path for actually storing content.
"""

import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY environment variable is not set. "
                "Get one at tavily.com and add it to .env"
            )
        _client = TavilyClient(api_key=api_key)
    return _client


def discover_urls(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """
    Returns a list of {url, title, snippet} candidates for the given topic.
    Raises RuntimeError if TAVILY_API_KEY is missing; raises whatever the
    Tavily SDK raises on a genuine API failure (rate limit, network, etc.)
    -- unlike ranker.py's fallback-on-failure design, there's no sensible
    fallback for "the search itself failed": there's nothing to show
    without it, so the caller (main.py) is responsible for turning this
    into a clean HTTP error rather than a broken response.
    """
    client = _get_client()
    response = client.search(query=query, max_results=max_results, search_depth="basic")

    results = []
    for item in response.get("results", []):
        url = item.get("url")
        if not url:
            continue  # defensive: skip anything malformed rather than crash the whole request
        results.append({
            "url": url,
            "title": item.get("title", "") or url,
            "snippet": item.get("content", "")[:300],  # Tavily's content can be long; trim for a preview-sized snippet
        })
    return results
