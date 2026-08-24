from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactStore:
    _artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def store(self, data: bytes, *, kind: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        artifact_id = uuid.uuid4().hex
        meta = dict(metadata or {})
        meta.setdefault("size", len(data))
        ref = {
            "url": f"artifact://{kind}/{artifact_id}",
            "kind": kind,
            "metadata": meta,
        }
        self._artifacts[artifact_id] = {"data": data, **ref}
        return ref

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        return self._artifacts.get(artifact_id)
