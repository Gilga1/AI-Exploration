"""The Phase 1 single-shot retrieve → generate RAG chain.

There is intentionally no agent state or loop in this module.  When LangChain
is installed, execution is wrapped in a ``RunnableLambda`` so callers use the
same ``invoke`` contract as later LangChain/LangGraph phases.  The module still
boots without it, which keeps the Phase 1 demo usable in an air-gapped setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.core.config import Settings, get_settings
from app.rag.corpus import CORPUS
from app.rag.embeddings import get_embedding_model
from app.rag.retriever import RagRetriever
from app.rag.vectorstore import InMemoryVectorStore, RagDocument
from app.telemetry.callback_bridge import LangChainOTelCallbackHandler

try:  # LangChain is optional at import time for the offline fallback.
    from langchain_core.runnables import RunnableLambda
except ImportError:  # pragma: no cover - exercised only before dependencies install
    RunnableLambda = None  # type: ignore[assignment,misc]


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


class OpenAIChatModel:
    """Adapter giving ChatOpenAI the ``provider_name`` the harness protocol expects."""

    provider_name = "openai"

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def invoke(self, prompt: str) -> Any:
        return self._inner.invoke(prompt)


def get_chat_model(settings: Settings) -> ChatModel:
    """Return the LLM-backed chat model; fail fast when no key is set.

    The harness is intentionally LLM-driven end to end — there is no offline
    stub fallback. A missing ``OPENAI_API_KEY`` is a configuration error so
    misconfigured deployments surface at startup instead of silently scoring
    against canned answers.
    """

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY (APP_OPENAI_API_KEY) is not configured. This harness "
            "is fully LLM-driven: set it in backend/.env before starting."
        )

    try:  # pragma: no cover - needs an explicitly configured external service
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OPENAI_API_KEY is configured but langchain-openai is missing. "
            "Install the 'openai' optional dependency: pip install -e '.[openai]'"
        ) from exc

    return OpenAIChatModel(
        ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
    )


class SingleShotRAGChain:
    """Retrieve relevant context once and ask one chat model to answer once."""

    def __init__(
        self,
        retriever: RagRetriever,
        chat_model: ChatModel,
        callback_handler: LangChainOTelCallbackHandler | None = None,
    ) -> None:
        self.retriever = retriever
        self.chat_model = chat_model
        # The bridge is deliberately attached to this simple Phase 1 chain. It
        # gives the eventual agent loop no special treatment and keeps the
        # LangChain/OTel integration isolated in one callback implementation.
        self.callback_handler = callback_handler or LangChainOTelCallbackHandler()
        self._runnable = RunnableLambda(self._run_with_trace) if RunnableLambda else None

    def invoke(self, question: str) -> RAGResult:
        """Execute the LangChain-wrapped single-shot RAG flow."""

        if not question or not question.strip():
            raise ValueError("question must not be empty")
        if self._runnable is not None:
            return self._runnable.invoke(question)
        return self._run_with_trace(question)

    def _run_with_trace(self, question: str) -> RAGResult:
        """Execute the fixed chain while emitting chain/retriever/LLM spans."""

        chain_run_id = uuid4()
        self.callback_handler.on_chain_start(
            {"name": "phase-1.retrieve-generate"},
            {"question": question},
            run_id=chain_run_id,
        )
        try:
            result = self._run_once(question, chain_run_id)
        except Exception as exc:
            self.callback_handler.on_chain_error(exc, run_id=chain_run_id)
            raise
        self.callback_handler.on_chain_end(
            {
                "answer": result.answer,
                "source_ids": result.source_ids,
                "llm_provider": result.llm_provider,
            },
            run_id=chain_run_id,
        )
        return result

    def _run_once(self, question: str, chain_run_id: UUID) -> RAGResult:
        retriever_run_id = uuid4()
        self.callback_handler.on_retriever_start(
            {"name": type(self.retriever).__name__},
            question,
            run_id=retriever_run_id,
            parent_run_id=chain_run_id,
        )
        try:
            documents = self.retriever.invoke(question)
        except Exception as exc:
            self.callback_handler.on_retriever_error(exc, run_id=retriever_run_id)
            raise
        self.callback_handler.on_retriever_end(documents, run_id=retriever_run_id)

        contexts = [document.page_content for document in documents]
        prompt = self._build_prompt(question, contexts)
        llm_run_id = uuid4()
        self.callback_handler.on_llm_start(
            {
                "name": type(self.chat_model).__name__,
                "provider": self.chat_model.provider_name,
            },
            [prompt],
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )
        try:
            response = self.chat_model.invoke(prompt)
        except Exception as exc:
            self.callback_handler.on_llm_error(exc, run_id=llm_run_id)
            raise
        self.callback_handler.on_llm_end(response, run_id=llm_run_id)
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
    return SingleShotRAGChain(
        retriever,
        get_chat_model(resolved_settings),
        callback_handler=LangChainOTelCallbackHandler(),
    )
