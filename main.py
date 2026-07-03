"""
FastAPI application exposing the content curator as an HTTP API.

Two endpoints, matching the original spec:
  POST /ingest    -- add one or more URLs to the index
  POST /recommend -- get ranked content recommendations for a reader profile

Design decision: the embedding model is loaded once at server STARTUP
(via the lifespan handler below), not on the first request. Without this,
whichever user's request happens to be first pays the multi-second model-load
cost. Loading it at startup means every request, including the first one,
gets consistent latency.
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from pipeline import ingest_urls, get_embedder, get_vectorstore
from auth import verify_api_key


def _rate_limit_key(request: Request) -> str:
    """
    Rate limit per API key, not per IP address. IP-based limiting is the
    slowapi default, but it's the wrong unit here: multiple legitimate
    callers can share an IP (behind a company NAT, for example), and a
    single bad actor can rotate IPs trivially. Since every caller already
    must send an API key, that's the correct identity to throttle on.
    Falls back to IP only for the edge case of a request with no key at
    all (which auth will reject anyway, before it can do any real damage).
    """
    return request.headers.get("X-API-Key") or get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: force the embedder and vector store to initialize now,
    # not lazily on first request.
    get_embedder()
    get_vectorstore()
    yield
    # Nothing to clean up on shutdown — ChromaDB's PersistentClient
    # writes to disk as it goes, no explicit close needed.


app = FastAPI(
    title="AI Content Curator",
    description="Ingest content from URLs, get ranked recommendations for a reader profile.",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---- Request/response schemas ----

class IngestRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, description="URLs to ingest (articles or YouTube videos)")
    skip_summary: bool = Field(
        default=False,
        description="If true, skips AI summarization (faster, free, but results won't have summaries). Useful for testing."
    )


class IngestResultResponse(BaseModel):
    url: str
    success: bool
    doc_id: str
    title: str
    error: str


class IngestResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[IngestResultResponse]


class RecommendRequest(BaseModel):
    profile: str = Field(..., min_length=1, description="Description of the reader and their goal, e.g. 'VP of Engineering who needs to understand LLMs in 30 minutes'")
    top_n: int = Field(default=5, ge=1, le=20, description="Number of results to return")


class RecommendationResponse(BaseModel):
    doc_id: str
    url: str
    title: str
    source_type: str
    summary: str
    score: float


class RecommendResponse(BaseModel):
    profile: str
    results: List[RecommendationResponse]


# ---- Endpoints ----

@app.post("/ingest", response_model=IngestResponse)
@limiter.limit("10/minute")  # strict: each call can trigger real Claude API cost per URL
def ingest(request: Request, body: IngestRequest, api_key: str = Depends(verify_api_key)) -> IngestResponse:
    results = ingest_urls(body.urls, skip_summary=body.skip_summary)
    succeeded = sum(1 for r in results if r.success)
    return IngestResponse(
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=[
            IngestResultResponse(url=r.url, success=r.success, doc_id=r.doc_id, title=r.title, error=r.error)
            for r in results
        ],
    )


@app.post("/recommend", response_model=RecommendResponse)
@limiter.limit("60/minute")  # looser: no LLM call here, just a vector lookup, much cheaper
def recommend(request: Request, body: RecommendRequest, api_key: str = Depends(verify_api_key)) -> RecommendResponse:
    raw_results = get_vectorstore().query(body.profile, top_n_documents=body.top_n)
    return RecommendResponse(
        profile=body.profile,
        results=[
            RecommendationResponse(
                doc_id=r["doc_id"],
                url=r["url"],
                title=r["title"],
                source_type=r["source_type"],
                summary=r["summary"],
                score=r["score"],
            )
            for r in raw_results
        ],
    )


@app.get("/health")
def health():
    """Basic liveness check -- also confirms how many chunks are currently indexed."""
    return {"status": "ok", "chunks_indexed": get_vectorstore().count()}
