"""Dense vector stores with metadata filters. ChromaDB by default; a numpy fallback with the same interface."""
from __future__ import annotations

from typing import Any

import numpy as np

Filter = dict[str, list[str]]  # meta key -> allowed values


def meta_ok(meta: dict[str, Any], flt: Filter | None) -> bool:
    if not flt:
        return True
    return all(str(meta.get(k, "")) in vals for k, vals in flt.items())


def _clean_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {k: (v if isinstance(v, (bool, int, float)) else str(v)) for k, v in meta.items()}


class NumpyStore:
    name = "numpy"

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.ids: list[str] = []
        self.metas: list[dict[str, Any]] = []
        self.mat = np.zeros((0, 1), np.float32)

    def add(self, ids: list[str], vecs: np.ndarray, metas: list[dict[str, Any]]) -> None:
        self.ids += ids
        self.metas += [_clean_meta(m) for m in metas]
        self.mat = vecs if self.mat.shape[0] == 0 else np.vstack([self.mat, vecs])

    def query(self, vec: np.ndarray, n: int, flt: Filter | None = None) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        sims = self.mat @ vec
        order = np.argsort(-sims)
        out = []
        for i in order:
            if meta_ok(self.metas[i], flt):
                out.append((self.ids[i], float(sims[i])))
                if len(out) >= n:
                    break
        return out


class ChromaStore:
    name = "chroma"

    def __init__(self, collection: str = "lni-knowledge"):
        import chromadb

        self._client = chromadb.EphemeralClient()
        self._name = collection
        self.reset()

    def reset(self) -> None:
        try:
            self._client.delete_collection(self._name)
        except Exception:
            pass
        self._col = self._client.create_collection(
            self._name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
        )

    def add(self, ids: list[str], vecs: np.ndarray, metas: list[dict[str, Any]]) -> None:
        for i in range(0, len(ids), 500):
            self._col.add(
                ids=ids[i : i + 500],
                embeddings=vecs[i : i + 500].tolist(),
                metadatas=[_clean_meta(m) for m in metas[i : i + 500]],
            )

    @staticmethod
    def _where(flt: Filter | None) -> dict[str, Any] | None:
        if not flt:
            return None
        conds = [{k: {"$in": [str(v) for v in vals]}} for k, vals in flt.items()]
        return conds[0] if len(conds) == 1 else {"$and": conds}

    def query(self, vec: np.ndarray, n: int, flt: Filter | None = None) -> list[tuple[str, float]]:
        count = self._col.count()
        if not count:
            return []
        res = self._col.query(query_embeddings=[vec.tolist()], n_results=min(n, count), where=self._where(flt))
        return [(i, 1.0 - float(d)) for i, d in zip(res["ids"][0], res["distances"][0])]


def make_store(backend: str):
    if backend == "chroma":
        try:
            return ChromaStore()
        except Exception as exc:  # keep the app usable if chroma is unavailable
            print(f"[index] ChromaDB unavailable ({exc}); using numpy vector store")
    return NumpyStore()
