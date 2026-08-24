"""A tiny, in-memory vector store for the fixed Phase 1 corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, Sequence


class EmbeddingModel(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does", "do", "for",
    "from", "how", "in", "is", "it", "of", "on", "or", "the", "to", "what",
    "when", "where", "which", "with",
}


def _content_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in _TOKEN_PATTERN.findall(text.lower()):
        if token in _STOP_WORDS:
            continue
        if token.endswith("ies") and len(token) > 4:
            token = f"{token[:-3]}y"
        elif token.endswith("ing") and len(token) > 5:
            token = token[:-3]
        elif token.endswith("s") and len(token) > 3:
            token = token[:-1]
        if token.endswith("e") and len(token) > 5:
            token = token[:-1]
        terms.add(token)
    return terms


def lexical_similarity(query: str, document: str) -> float:
    """Lightly rerank hash vectors by exact content-term overlap.

    This small hybrid component avoids hash collisions overwhelming a short,
    high-signal corpus while retaining the configured embedding model as the
    vector-store's primary representation.
    """

    query_terms = _content_terms(query)
    document_terms = _content_terms(document)
    if not query_terms or not document_terms:
        return 0.0
    return len(query_terms & document_terms) / (len(query_terms) * len(document_terms)) ** 0.5


@dataclass(frozen=True)
class RagDocument:
    """Minimal document shape shared by the retriever, chain, and evaluator."""

    page_content: str
    metadata: dict[str, str] = field(default_factory=dict)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return a cosine score; zero vectors are treated as unrelated."""

    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_size = sum(a * a for a in left) ** 0.5
    right_size = sum(b * b for b in right) ** 0.5
    if not left_size or not right_size:
        return 0.0
    return numerator / (left_size * right_size)


class InMemoryVectorStore:
    """Immutable document index with a LangChain-like similarity search API."""

    def __init__(self, documents: Sequence[RagDocument], embedding_model: EmbeddingModel) -> None:
        self.documents = list(documents)
        self.embedding_model = embedding_model
        self._vectors = embedding_model.embed_documents(
            [document.page_content for document in self.documents]
        )

    @classmethod
    def from_documents(
        cls, documents: Sequence[RagDocument], embedding_model: EmbeddingModel
    ) -> "InMemoryVectorStore":
        return cls(documents, embedding_model)

    def similarity_search_with_relevance_scores(
        self, query: str, k: int = 3
    ) -> list[tuple[RagDocument, float]]:
        if k < 1:
            return []
        query_vector = self.embedding_model.embed_query(query)
        ranked = []
        for document, vector in zip(self.documents, self._vectors, strict=True):
            vector_score = cosine_similarity(query_vector, vector)
            score = (0.25 * vector_score) + (0.75 * lexical_similarity(query, document.page_content))
            ranked.append((document, score))
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:k]

    def similarity_search(self, query: str, k: int = 3) -> list[RagDocument]:
        return [document for document, _ in self.similarity_search_with_relevance_scores(query, k)]
