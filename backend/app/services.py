"""The knowledge base: loads/ingests data, owns the index, searcher, fingerprinter and persistence."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

from .agent.fingerprint import Fingerprinter
from .config import Settings
from .ingest.chunker import log_chunks, mop_chunks, record_chunks
from .ingest.loaders import scan
from .ingest.structure import FieldMapper, parse_log, parse_mop, parse_tests, to_record
from .rag.index import KnowledgeIndex
from .rag.models import CrossEncoderReranker, EmbeddingCache, make_embedder
from .rag.search import HybridSearcher
from .rag.vectorstore import make_store
from .schemas import IngestResponse, LNIRecord, LogSnippet, MopDoc
from .store.db import Store
from .textutil import find_nodes


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.store_dir / "kb.sqlite")
        self.mapper = FieldMapper(settings.field_map)
        self.records: dict[str, LNIRecord] = {}
        self.mops: dict[str, MopDoc] = {}
        self.logs: dict[str, LogSnippet] = {}
        self.tests: list[dict[str, Any]] = []
        self.fingerprinter = Fingerprinter()
        self.lock = threading.RLock()
        self.ready = False

        s = settings
        self.embedder = make_embedder(s.embed_backend, s.embed_model, s.models_dir)
        slug = re.sub(r"[^a-z0-9]+", "-", self.embedder.name.lower())
        cache = EmbeddingCache(s.store_dir / f"emb-{slug}.npz", self.embedder)
        self.reranker = None
        if s.use_reranker and s.embed_backend != "hash":
            try:
                self.reranker = CrossEncoderReranker(s.rerank_model, s.models_dir, s.rerank_temperature)
            except Exception as exc:
                print(f"[kb] reranker unavailable ({exc}); continuing without it")
        self.index = KnowledgeIndex(cache, make_store(s.vector_backend))
        self.searcher = HybridSearcher(self.index, self.embedder, self.reranker, self.records, self.logs,
                                       s.duplicate_similarity)

    # ---------- lifecycle ----------
    def startup(self) -> None:
        self._load_from_store()
        if not any(r.source == "dataset" for r in self.records.values()) and self.settings.data_dir.exists():
            self.ingest()
        else:
            self._load_tests(self.settings.data_dir)
            self.rebuild_index()
        self.ready = True

    def _load_from_store(self) -> None:
        self.records.clear()
        self.records.update({d["id"]: LNIRecord(**d) for d in self.store.all("records")})
        self.mops.clear()
        self.mops.update({d["mop_id"]: MopDoc(**d) for d in self.store.all("mops")})
        self.logs.clear()
        self.logs.update({d["id"]: LogSnippet(**d) for d in self.store.all("logs")})

    def _load_tests(self, root: Path) -> None:
        if root.exists():
            ds = scan(root, self.mapper.aliases_for("tests", "expected"))
            self.tests = parse_tests(ds.tests, self.mapper)

    def rebuild_index(self) -> None:
        chunks = [c for r in self.records.values() for c in record_chunks(r)]
        chunks += [c for m in self.mops.values() for c in mop_chunks(m)]
        chunks += [c for lg in self.logs.values() for c in log_chunks(lg)]
        self.index.build(chunks)
        self.fingerprinter.refresh(list(self.records.values()), list(self.mops.values()))

    # ---------- ingestion ----------
    def ingest(self, path: str | None = None, raw_records: list[dict[str, Any]] | None = None,
               reset: bool = True) -> IngestResponse:
        t0 = time.time()
        with self.lock:
            if raw_records is not None:
                new = [to_record(r, self.mapper, len(self.records) + i) for i, r in enumerate(raw_records, 1)]
                if reset:
                    self._drop_dataset_records()
            else:
                root = Path(path) if path else self.settings.data_dir
                ds = scan(root, self.mapper.aliases_for("tests", "expected"))
                new = [to_record(r, self.mapper, i) for i, r in enumerate(ds.records, 1)]
                self._drop_dataset_records()
                mops = [parse_mop(n, t) for n, t in ds.mops]
                logs = [parse_log(n, t, i) for i, (n, t) in enumerate(ds.logs, 1)]
                self.mops.clear()
                self.mops.update({m.mop_id: m for m in mops if m.steps})
                self.logs.clear()
                self.logs.update({lg.id: lg for lg in logs})
                self.store.clear("mops")
                self.store.clear("logs")
                self.store.upsert_many("mops", [(m.mop_id, m.model_dump(), "") for m in self.mops.values()])
                self.store.upsert_many("logs", [(lg.id, lg.model_dump(), "") for lg in self.logs.values()])
                self.tests = parse_tests(ds.tests, self.mapper)
                self._seed_tickets()
            for r in new:
                self.records[r.id] = r
            self.store.upsert_many("records", [(r.id, r.model_dump(), r.source) for r in new])
            self.rebuild_index()
        return IngestResponse(**self.stats(), seconds=round(time.time() - t0, 2))

    def _drop_dataset_records(self) -> None:
        for rid in [k for k, r in self.records.items() if r.source == "dataset"]:
            del self.records[rid]
        self.store.clear("records", source="dataset")

    def _seed_tickets(self) -> None:
        """Mock ticketing system: open tickets created from the test incidents (without their answers)."""
        if self.store.count("tickets"):
            return
        rows = []
        for i, t in enumerate(self.tests, start=1):
            kind = "change" if t["mode"] == "pre_change" else "incident"
            tid = f"{'CHG' if kind == 'change' else 'INC'}-{5000 + i}"
            nodes = find_nodes(t["text"])
            rows.append((tid, {"id": tid, "type": kind, "status": "Open", "summary": t["text"],
                               "node": nodes[0] if nodes else "", "learnings": []}, kind))
        self.store.upsert_many("tickets", rows)

    # ---------- write-back ----------
    def add_record(self, r: LNIRecord) -> None:
        with self.lock:
            self.records[r.id] = r
            self.store.upsert("records", r.id, r.model_dump(), r.source)
            self.index.add(record_chunks(r))
            self.fingerprinter.refresh(list(self.records.values()), list(self.mops.values()))

    def save_record(self, r: LNIRecord) -> None:
        with self.lock:
            self.records[r.id] = r
            self.store.upsert("records", r.id, r.model_dump(), r.source)

    def delete_record(self, record_id: str) -> LNIRecord:
        """Delete a lesson saved by an engineer (LRN-...). Records from the dataset cannot be deleted here."""
        with self.lock:
            r = self.records.get(record_id)
            if not r:
                raise KeyError(record_id)
            if r.source != "learning":
                raise PermissionError(f"{record_id} comes from the dataset; only saved lessons can be deleted")
            del self.records[record_id]
            self.store.delete("records", record_id)
            # remove the note this lesson left on its ticket; reopen the ticket if nothing else resolved it
            for t in self.store.all("tickets"):
                notes = t.get("learnings", [])
                if not any(n.get("record_id") == record_id for n in notes):
                    continue
                kept = []
                for n in notes:
                    if n.get("record_id") != record_id:
                        kept.append(n)
                    elif n.get("confirmed_ids"):  # the same note also confirmed a fix: keep that part
                        kept.append({**n, "record_id": None, "root_cause": "", "fix": ""})
                t["learnings"] = kept
                if not kept:
                    t["status"] = "Open"
                self.store.upsert("tickets", t["id"], t, t.get("type", ""))
            self.rebuild_index()  # embeddings are cached, so this is quick
        return r

    def next_learning_id(self) -> str:
        n = sum(1 for r in self.records.values() if r.source == "learning") + 1
        while f"LRN-{n:04d}" in self.records:
            n += 1
        return f"LRN-{n:04d}"

    def stats(self) -> dict[str, int]:
        recs = list(self.records.values())
        return {
            "records": sum(1 for r in recs if r.source == "dataset"),
            "learnings": sum(1 for r in recs if r.source == "learning"),
            "mops": len(self.mops),
            "mop_steps": sum(len(m.steps) for m in self.mops.values()),
            "logs": len(self.logs),
            "chunks": len(self.index),
            "tickets": self.store.count("tickets"),
        }


_kb: KnowledgeBase | None = None
_agent = None


def get_kb() -> KnowledgeBase:
    if _kb is None:
        raise RuntimeError("Knowledge base not initialised")
    return _kb


def get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialised")
    return _agent


def init_services(settings: Settings):
    """Create the knowledge base and the agent (called once at app start-up)."""
    from .agent.llm import LLMClient
    from .agent.runner import Agent

    global _kb, _agent
    _kb = KnowledgeBase(settings)
    _kb.startup()
    _agent = Agent(_kb, settings, LLMClient(settings))
    return _kb, _agent
