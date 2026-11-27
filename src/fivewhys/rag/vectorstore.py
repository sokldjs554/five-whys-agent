"""인메모리 벡터 저장소 (numpy 코사인 유사도 top-k)."""

from __future__ import annotations

import numpy as np


class VectorStore:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._ids: list[int] = []
        self._matrix = np.zeros((0, dim), dtype=np.float32)

    def add(self, chunk_id: int, vector: list[float]) -> None:
        self.add_batch([chunk_id], [vector])

    def add_batch(self, chunk_ids: list[int], vectors: list[list[float]]) -> None:
        if not chunk_ids and not len(vectors):
            return
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.shape != (len(chunk_ids), self.dim):
            raise ValueError("Vector IDs and dimensions must align")
        self._matrix = np.vstack([self._matrix, matrix])
        self._ids.extend(chunk_ids)

    def search(self, query_vector: list[float], k: int = 10, *, allowed_ids: set[int] | None = None) -> list[tuple[int, float]]:
        if not self._ids:
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        # 벡터는 임베딩 단계에서 L2 정규화되어 있으므로 내적 == 코사인 유사도
        scores = self._matrix @ q
        indices = np.arange(len(scores)) if allowed_ids is None else np.array(
            [i for i, chunk_id in enumerate(self._ids) if chunk_id in allowed_ids], dtype=int
        )
        order = indices[np.argsort(-scores[indices])[:k]]
        return [(self._ids[i], float(scores[i])) for i in order]

    def __len__(self) -> int:
        return len(self._ids)
