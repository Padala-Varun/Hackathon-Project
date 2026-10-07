"""Embedding + reranker models (Hugging Face weights, run locally) and an on-disk embedding cache."""
from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.clip(norms, 1e-9, None)


class FastEmbedder:
    def __init__(self, model: str, cache_dir: Path):
        from fastembed import TextEmbedding

        self.name = model
        self._m = TextEmbedding(model, cache_dir=str(cache_dir))

    def passages(self, texts: list[str]) -> np.ndarray:
        return _normalize(np.array(list(self._m.passage_embed(texts)), dtype=np.float32))

    def query(self, text: str) -> np.ndarray:
        return _normalize(np.array(list(self._m.query_embed([text]))[0], dtype=np.float32))


class STEmbedder:
    def __init__(self, model: str, cache_dir: Path):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.name = model
        self._m = SentenceTransformer(model, cache_folder=str(cache_dir))

    def passages(self, texts: list[str]) -> np.ndarray:
        return self._m.encode(texts, normalize_embeddings=True).astype(np.float32)

    def query(self, text: str) -> np.ndarray:
        prefix = "Represent this sentence for searching relevant passages: " if "bge" in self.name.lower() else ""
        return self._m.encode([prefix + text], normalize_embeddings=True)[0].astype(np.float32)


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder. Offline, instant - used by the unit tests."""

    name = "hash-256"

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(256, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % 256] += 1.0 if (h >> 9) & 1 else -1.0
        return v

    def passages(self, texts: list[str]) -> np.ndarray:
        return _normalize(np.stack([self._vec(t) for t in texts])) if texts else np.zeros((0, 256), np.float32)

    def query(self, text: str) -> np.ndarray:
        return _normalize(self._vec(text))


def make_embedder(backend: str, model: str, cache_dir: Path):
    if backend == "hash":
        return HashEmbedder()
    if backend == "sentence-transformers":
        return STEmbedder(model, cache_dir)
    return FastEmbedder(model, cache_dir)


class EmbeddingCache:
    """sha1(text) -> vector, persisted as .npz so restarts and re-ingests don't re-embed unchanged chunks."""

    def __init__(self, path: Path, embedder):
        self.path, self.embedder = path, embedder
        self._d: dict[str, np.ndarray] = {}
        if path.exists():
            with np.load(path) as z:
                self._d = {k: z[k] for k in z.files}

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def embed(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if self.key(t) not in self._d]
        if missing:
            for t, v in zip(missing, self.embedder.passages(missing)):
                self._d[self.key(t)] = v
            self.path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(self.path, **self._d)
        if not texts:
            return np.zeros((0, 1), np.float32)
        return np.stack([self._d[self.key(t)] for t in texts])


class CrossEncoderReranker:
    def __init__(self, model: str, cache_dir: Path, temperature: float = 0):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.name = model
        self.temperature = temperature or (2.5 if "ms-marco" in model.lower() else 1.0)
        self._m = TextCrossEncoder(model, cache_dir=str(cache_dir))

    def scores(self, query: str, docs: list[str]) -> list[float]:
        """Relevance probability 0..1 for each doc (sigmoid of the cross-encoder logit)."""
        if not docs:
            return []
        return [1.0 / (1.0 + math.exp(-float(s) / self.temperature)) for s in self._m.rerank(query, docs)]
