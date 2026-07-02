"""
Embedding layer.

The rest of the system (chunking, storage, retrieval) should never know or care
HOW text gets turned into a vector. It just calls `embedder.embed(texts)` and
gets vectors back. This is the interface pattern: define a contract (EmbeddingProvider),
then write implementations against it.

Why this matters concretely: today you're using a local model. Later, if you want
better retrieval quality, you swap in an API-based provider (OpenAI, Voyage). If
everything downstream just talks to EmbeddingProvider, that swap is a one-line
change in config.py — not a rewrite of your pipeline.
"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Contract every embedding backend must satisfy."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Turn a list of strings into a list of vectors (same order)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector size this provider produces. ChromaDB needs to know this upfront."""
        raise NotImplementedError


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Runs a small open-source model on your own machine. No API key, no network
    call, no cost. Model: all-MiniLM-L6-v2 — 80MB, 384-dimensional vectors,
    fast on CPU. It's not the best embedding model that exists, but it's good
    enough to prove retrieval works, which is what an MVP needs to do.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Imported here, not at module top, so that importing this file doesn't
        # force-load torch/sentence-transformers if you end up only using the
        # API provider. Small thing, but keeps startup fast later.
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self._dimension = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return vectors.tolist()

    @property
    def dimension(self) -> int:
        return self._dimension


class APIEmbeddingProvider(EmbeddingProvider):
    """
    Placeholder for later. Note: Anthropic (Claude) does not offer an embeddings
    API — if you want a hosted API provider, the real candidates are OpenAI
    (text-embedding-3-small) or Voyage AI. Not implementing this now since you
    chose local — but the shape is here so you can see exactly what needs
    filling in when you're ready.
    """

    def __init__(self, api_key: str, model: str = "voyage-3-lite"):
        raise NotImplementedError(
            "Wire this up when you're ready to switch. "
            "You'll call the provider's embeddings endpoint here instead of a local model."
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        raise NotImplementedError
