"""The Phase 1 single-shot retrieve → generate RAG chain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from app.core.config import Settings, get_settings
from app.core.llm import ChatModel, get_chat_model
from app.rag.corpus import CORPUS
from app.rag.embeddings import get_embedding_model
from app.rag.retriever import RagRetriever
from app.rag.vectorstore import InMemoryVectorStore
from app.telemetry.callback_bridge import LangChainOTelCallbackHandler

try:
    from langchain_core.runnables import RunnableLambda
except ImportError:
    RunnableLambda = None  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class RAGResult:
    """Structured result that evaluation code can turn into an LLM test case."""

    question: str
    answer: str
    contexts: list[str]
    source_ids: list[str]
    llm_provider: str
    trace_id: str | None = None


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
        self.callback_handler = callback_handler or LangChainOTelCallbackHandler()
        self._runnable = RunnableLambda(self._run_with_trace) if RunnableLambda else None

    def invoke(self, question: str) -> RAGResult:
        if not question or not question.strip():
            raise ValueError("question must not be empty")
        if self._runnable is not None:
            return self._runnable.invoke(question)
        return self._run_with_trace(question)

    def _run_with_trace(self, question: str) -> RAGResult:
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
        trace_id = self.callback_handler.last_trace_id(str(chain_run_id))
        if trace_id is None:
            trace_id = self.callback_handler.last_completed_trace_id()
        return RAGResult(
            question=result.question,
            answer=result.answer,
            contexts=result.contexts,
            source_ids=result.source_ids,
            llm_provider=result.llm_provider,
            trace_id=trace_id,
        )

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


def build_phase_one_chain(
    settings: Settings | None = None,
    callback_handler: LangChainOTelCallbackHandler | None = None,
) -> SingleShotRAGChain:
    """Build the fixed-corpus Phase 1 chain from application settings."""

    resolved_settings = settings or get_settings()
    vector_store = InMemoryVectorStore.from_documents(
        CORPUS, get_embedding_model(resolved_settings)
    )
    retriever = RagRetriever(vector_store, resolved_settings.rag_retrieval_k)
    return SingleShotRAGChain(
        retriever,
        get_chat_model(resolved_settings),
        callback_handler=callback_handler or LangChainOTelCallbackHandler(),
    )
