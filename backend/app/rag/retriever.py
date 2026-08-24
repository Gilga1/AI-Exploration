"""Retriever facade over the Phase 1 in-memory vector store."""

from __future__ import annotations

from app.rag.vectorstore import InMemoryVectorStore, RagDocument


class RagRetriever:
    """A callable/invokable retriever compatible with simple LangChain flows."""

    def __init__(self, vector_store: InMemoryVectorStore, k: int = 3) -> None:
        self.vector_store = vector_store
        self.k = k

    def invoke(self, query: str) -> list[RagDocument]:
        return self.get_relevant_documents(query)

    def get_relevant_documents(self, query: str) -> list[RagDocument]:
        return self.vector_store.similarity_search(query, self.k)

    def get_relevant_documents_with_scores(
        self, query: str
    ) -> list[tuple[RagDocument, float]]:
        return self.vector_store.similarity_search_with_relevance_scores(query, self.k)
