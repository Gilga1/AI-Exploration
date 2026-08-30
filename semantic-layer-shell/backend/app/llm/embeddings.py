from __future__ import annotations

import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                kwargs["base_url"] = self.settings.openai_base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def embed(self, text: str) -> list[float]:
        if not self.enabled or not text.strip():
            return [0.0] * self.settings.embedding_dimensions

        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=text,
            )
            vector = response.data[0].embedding
            if len(vector) != self.settings.embedding_dimensions:
                logger.warning(
                    "Embedding dimension mismatch: got %d, expected %d",
                    len(vector),
                    self.settings.embedding_dimensions,
                )
            return vector
        except Exception as exc:
            logger.warning("Embedding failed, using zero vector: %s", exc)
            return [0.0] * self.settings.embedding_dimensions
