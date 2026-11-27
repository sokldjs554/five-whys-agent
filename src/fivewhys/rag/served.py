"""Batched HTTP adapter for the optional multilingual MiniLM encoder."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

import numpy as np


def checked_vectors(rows, count, dim):
    matrix = np.asarray(rows, dtype=np.float32)
    if matrix.shape != (count, dim) or not np.isfinite(matrix).all():
        raise ValueError("Embedding response has invalid shape or values")
    if not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=0.002):
        raise ValueError("Embedding service must return unit vectors")
    return matrix.tolist()


class ServedEmbedder:
    dim = 384

    def __init__(self, url: str):
        self.url = url

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"texts": texts}).encode()
        request = Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Embedding response too large")
        return checked_vectors(json.loads(raw)["vectors"], len(texts), self.dim)

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]
