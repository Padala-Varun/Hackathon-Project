"""Knowledge index: dense vectors (Chroma/numpy) + BM25 over the same field-level chunks."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from rank_bm25 import BM25Okapi

from ..schemas import Chunk
from .models import EmbeddingCache
from .tokenizer import tokenize
from .vectorstore import Filter, meta_ok


class KnowledgeIndex:
    def __init__(self, cache: EmbeddingCache, store):
        self.cache, self.store = cache, store
        self.chunks: dict[str, Chunk] = {}
        self.vecs: dict[str, np.ndarray] = {}
        self.by_record: dict[str, list[str]] = defaultdict(list)
        self._order: list[str] = []
        self._tokens: dict[str, list[str]] = {}
        self._bm25: BM25Okapi | None = None

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks.clear()
        self.vecs.clear()
        self.by_record.clear()
        self._order.clear()
        self._tokens.clear()
        self.store.reset()
        self.add(chunks)

    def add(self, chunks: list[Chunk]) -> None:
        chunks = [c for c in chunks if c.id not in self.chunks]
        if not chunks:
            return
        vecs = self.cache.embed([c.text for c in chunks])
        for c, v in zip(chunks, vecs):
            self.chunks[c.id] = c
            self.vecs[c.id] = v
            self.by_record[c.record_id].append(c.id)
            self._order.append(c.id)
            self._tokens[c.id] = tokenize(c.text)
        self.store.add([c.id for c in chunks], vecs, [c.meta for c in chunks])
        self._bm25 = BM25Okapi([self._tokens[i] for i in self._order])

    def __len__(self) -> int:
        return len(self._order)

    def tokens(self, chunk_id: str) -> list[str]:
        return self._tokens.get(chunk_id, [])

    def sim(self, qvec: np.ndarray, chunk_id: str) -> float:
        return float(self.vecs[chunk_id] @ qvec)

    def dense_search(self, qvec: np.ndarray, n: int, flt: Filter | None = None) -> list[tuple[str, float]]:
        return self.store.query(qvec, n, flt)

    def bm25_search(self, query: str, n: int, flt: Filter | None = None) -> list[tuple[str, float]]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        order = np.argsort(-scores)
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            cid = self._order[i]
            if meta_ok(self.chunks[cid].meta, flt):
                out.append((cid, float(scores[i])))
                if len(out) >= n:
                    break
        return out
