"""Text embedding behind a small interface so the model can be swapped (or faked in tests)."""

import hashlib
import re
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedder:
    """Local ONNX embedding model (default: BAAI/bge-small-en-v1.5, 384 dims).

    Runs on CPU inside the API container: no API key, no per-token cost, and document
    text never leaves the machine. Vectors come back L2-normalised, so cosine == dot.
    """

    def __init__(self, model_name: str, dim: int):
        from fastembed import TextEmbedding  # heavy import; keep it out of test paths

        self._model = TextEmbedding(model_name=model_name)
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return list(self._model.passage_embed(texts, batch_size=32))

    def embed_query(self, text: str) -> np.ndarray:
        return next(iter(self._model.query_embed(text)))


class HashEmbedder:
    """Deterministic bag-of-words embedding for tests. Similar wording -> similar vectors."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
            vec[bucket] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)
