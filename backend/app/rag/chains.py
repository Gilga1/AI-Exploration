"""The Phase 1 single-shot retrieve → generate RAG chain.

There is intentionally no agent state or loop in this module.  When LangChain
is installed, execution is wrapped in a ``RunnableLambda`` so callers use the
same ``invoke`` contract as later LangChain/LangGraph phases.  The module still
boots without it, which keeps the Phase 1 demo usable in an air-gapped setup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.rag.corpus import CORPUS
from app.rag.embeddings import get_embedding_model
from app.rag.retriever import RagRetriever
from app.rag.vectorstore import InMemoryVectorStore, RagDocument

try:  # LangChain is optional at import time for the offline fallback.
    from langchain_core.runnables import RunnableLambda
except ImportError:  # pragma: no cover - exercised only before dependencies install
    RunnableLambda = None  # type: ignore[assignment,misc]


_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does", "do", "for",
    "from", "how", "in", "is", "it", "of", "on", "or", "the", "to", "what",
    "when", "where", "which", "with",
}


def _content_terms(text: str) -> set[str]:
    """Normalise enough morphology for the deterministic extractive stub."""

    terms: set[str] = set()
    for token in _WORD_PATTERN.findall(text.lower()):
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


@dataclass(frozen=True)
class RAGResult:
    """Structured result that evaluation code can turn into an LLM test case."""

    question: str
    answer: str
    contexts: list[str]
    source_ids: list[str]
    llm_provider: str


class ChatModel(Protocol):
    provider_name: str

    def invoke(self, prompt: str) -> Any: ...


class OfflineContextChatModel:
    """A deterministic extractive chat-model stub used without an API key."""

    provider_name = "offline-stub"

    def invoke(self, prompt: str) -> str:
        prompt_prefix, context = prompt.split("\n\nContext:\n", maxsplit=1)
        question = prompt_prefix.rsplit("\n", maxsplit=1)[-1].removeprefix("Question: ")
        query_terms = _content_terms(question)
        # The retriever orders documents by relevance. Restricting the
        # deterministic stub to that top document makes its extractive answer
        # predictable while a configured real chat model still receives all
        # retrieved context.
        top_context = re.split(r"\n\n\[Document \d+\]\n", context, maxsplit=1)[0]
        top_context = re.sub(r"^\[Document \d+\]\n", "", top_context)
        sentences = [
            sentence.strip().removeprefix("- ")
            for sentence in _SENTENCE_PATTERN.split(top_context.replace("\n", " "))
            if sentence.strip()
        ]
        if not sentences:
            return "I do not have enough context to answer that question."

        def relevance(sentence: str) -> tuple[int, int]:
            sentence_terms = _content_terms(sentence)
            return (len(query_terms & sentence_terms), -len(sentence))

        # Returning a source sentence ensures an offline answer is grounded in
        # the retrieval context rather than inventing unsupported facts.
        return max(sentences, key=relevance)


def get_chat_model(settings: Settings) -> ChatModel:
    """Use a configured real chat model, otherwise the deterministic stub."""

    if not settings.openai_api_key:
        return OfflineContextChatModel()

    try:  # pragma: no cover - needs an explicitly configured external service
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OPENAI_API_KEY is configured but langchain-openai is missing. "
            "Install the 'openai' optional dependency."
        ) from exc

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )


class SingleShotRAGChain:
    """Retrieve relevant context once and ask one chat model to answer once."""

    def __init__(self, retriever: RagRetriever, chat_model: ChatModel) -> None:
        self.retriever = retriever
        self.chat_model = chat_model
        self._runnable = RunnableLambda(self._run_once) if RunnableLambda else None

    def invoke(self, question: str) -> RAGResult:
        """Execute the LangChain-wrapped single-shot RAG flow."""

        if not question or not question.strip():
            raise ValueError("question must not be empty")
        if self._runnable is not None:
            return self._runnable.invoke(question)
        return self._run_once(question)

    def _run_once(self, question: str) -> RAGResult:
        documents = self.retriever.invoke(question)
        contexts = [document.page_content for document in documents]
        prompt = self._build_prompt(question, contexts)
        response = self.chat_model.invoke(prompt)
        answer = self._response_text(response)
        return RAGResult(
            question=question,
            answer=answer,
            contexts=contexts,
            source_ids=[document.metadata.get("id", "unknown") for document in documents],
            llm_provider=self.chat_model.provider_name,
        )

    @staticmethod
    def _build_prompt(question: str, contexts: list[str]) -> str:
        joined_context = "\n\n".join(
            f"[Document {index}]\n{context}" for index, context in enumerate(contexts, start=1)
        )
        return (
            "Answer the question using only the supplied context. If the answer is not "
            "present, say that you do not have enough context.\n"
            f"Question: {question}\n\nContext:\n{joined_context}"
        )

    @staticmethod
    def _response_text(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            ).strip()
        return str(content).strip()


def build_phase_one_chain(settings: Settings | None = None) -> SingleShotRAGChain:
    """Build the fixed-corpus Phase 1 chain from application settings."""

    resolved_settings = settings or get_settings()
    vector_store = InMemoryVectorStore.from_documents(
        CORPUS, get_embedding_model(resolved_settings)
    )
    retriever = RagRetriever(vector_store, resolved_settings.rag_retrieval_k)
    return SingleShotRAGChain(retriever, get_chat_model(resolved_settings))
