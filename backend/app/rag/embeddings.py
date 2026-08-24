"""Embedding adapters with a deterministic, download-free default.

`HashEmbeddingModel` deliberately has the small ``Embeddings``-style surface
used by LangChain: ``embed_documents`` and ``embed_query``.  It is suitable for
the fixed Phase 1 corpus and makes local/CI runs independent of external model
downloads.  Set ``APP_RAG_EMBEDDING_MODEL`` to a Sentence Transformers model
name to opt into a real local model (after installing the optional extra).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from app.core.config import Settings

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class HashEmbeddingModel:
    """A stable signed-hashing bag-of-words embedding model.

    Hashing is deterministic across Python processes (unlike ``hash()``), and
    L2 normalisation makes the vectors usable with cosine similarity.
    """

    def __init__(self, dimension: int = 256) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude:
            vector = [value / magnitude for value in vector]
        return vector


class SentenceTransformerEmbeddingModel:
    """Lazy adapter for an explicitly configured Sentence Transformers model."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError(
                "APP_RAG_EMBEDDING_MODEL requires the 'local-embeddings' "
                "optional dependency: pip install -e '.[local-embeddings]'"
            ) from exc

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]


def get_embedding_model(settings: Settings) -> HashEmbeddingModel | SentenceTransformerEmbeddingModel:
    """Return the requested local model, falling back to deterministic hashing."""

    if settings.rag_embedding_model:
        return SentenceTransformerEmbeddingModel(settings.rag_embedding_model)
    return HashEmbeddingModel(settings.rag_embedding_dimension)
