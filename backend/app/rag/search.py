"""Hybrid search: dense + BM25 (with metadata filters) -> RRF pooling -> cross-encoder rerank
-> aggregate chunks to records -> fingerprint bonus -> confidence 0-100 -> group reworded duplicates."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ..schemas import Chunk, DuplicateRef, Evidence, Fingerprint, LNIRecord, LogSnippet, Match, MopDoc, MopStep
from .index import KnowledgeIndex
from .tokenizer import tokenize
from .vectorstore import Filter

# bge-small cosine similarities sit roughly in 0.55 (unrelated) .. 0.92 (same problem); map to 0..1.
COS_LOW, COS_HIGH = 0.62, 0.88
RRF_K = 60
MATCH_FIELDS = ["symptom", "change", "root_cause", "resolution", "learning", "details", "log"]


def cos_scaled(sim: float) -> float:
    return float(min(1.0, max(0.0, (sim - COS_LOW) / (COS_HIGH - COS_LOW))))


@dataclass
class SearchConfig:
    dense: bool = True
    bm25: bool = True
    rerank: bool = True
    fingerprint: bool = True
    candidates: int = 30


@dataclass
class Scored:
    chunk: Chunk
    dense: float
    bm25: float
    rerank: float | None
    rel: float


def _strip_header(text: str) -> str:
    return text.split("] ", 1)[1] if text.startswith("[") and "] " in text else text


class HybridSearcher:
    def __init__(self, index: KnowledgeIndex, embedder, reranker, records: dict[str, LNIRecord],
                 logs: dict[str, LogSnippet], duplicate_similarity: float = 0.88):
        self.index, self.embedder, self.reranker = index, embedder, reranker
        self.records, self.logs = records, logs
        self.dup_sim = duplicate_similarity

    # ---------- chunk level ----------
    def chunk_search(self, query: str, flt: Filter | None, cfg: SearchConfig, qvec=None) -> list[Scored]:
        qvec = self.embedder.query(query) if qvec is None else qvec
        dense = self.index.dense_search(qvec, cfg.candidates, flt) if cfg.dense else []
        bm25 = self.index.bm25_search(query, cfg.candidates, flt) if cfg.bm25 else []
        rrf: dict[str, float] = defaultdict(float)
        for lst in (dense, bm25):
            for rank, (cid, _) in enumerate(lst):
                rrf[cid] += 1.0 / (RRF_K + rank + 1)
        cands = sorted(rrf, key=rrf.get, reverse=True)[: cfg.candidates]
        if not cands:
            return []
        bm = dict(bm25)
        bm_max = max(bm.values()) if bm else 1.0
        probs = (
            self.reranker.scores(query, [_strip_header(self.index.chunks[c].text) for c in cands])
            if cfg.rerank and self.reranker
            else [None] * len(cands)
        )
        out = []
        for cid, p in zip(cands, probs):
            d = self.index.sim(qvec, cid)
            b = bm.get(cid, 0.0) / bm_max if bm_max else 0.0
            if p is not None:
                rel = 0.6 * p + 0.25 * cos_scaled(d) + 0.15 * b
            elif cfg.dense and cfg.bm25:
                rel = 0.75 * cos_scaled(d) + 0.25 * b
            elif cfg.dense:
                rel = cos_scaled(d)
            else:
                rel = b
            out.append(Scored(self.index.chunks[cid], d, b, p, rel))
        out.sort(key=lambda s: s.rel, reverse=True)
        return out

    # ---------- record level ----------
    def match_records(self, query: str, flt: dict[str, str] | None = None, fp: Fingerprint | None = None,
                      top_k: int = 5, cfg: SearchConfig | None = None, fields: list[str] | None = None,
                      group: bool = True) -> list[Match]:
        cfg = cfg or SearchConfig()
        chunk_flt: Filter = {"field": fields or MATCH_FIELDS}
        for k, v in (flt or {}).items():
            chunk_flt[k] = [v]
        # Logs carry no node-type metadata, so a metadata filter naturally restricts the search to LNI chunks.
        scored = self.chunk_search(query, chunk_flt, cfg)
        per_record: dict[str, list[Scored]] = defaultdict(list)
        for s in scored:
            if s.chunk.kind == "lni":
                per_record[s.chunk.record_id].append(s)
            elif s.chunk.kind == "log":
                log = self.logs.get(s.chunk.record_id)
                for rid in (log.related_ids if log else []):
                    per_record[rid].append(Scored(s.chunk, s.dense, s.bm25, s.rerank, s.rel * 0.9))
        q_tokens = {t for t in tokenize(query) if len(t) > 2}
        matches = []
        for rid, lst in per_record.items():
            r = self.records.get(rid)
            if not r or not r.is_problem:
                continue
            lst.sort(key=lambda s: s.rel, reverse=True)
            best = lst[0]
            support = sum(1 for s in lst[1:] if s.rel > 0.5)
            base = min(1.0, best.rel + 0.03 * min(support, 2))
            reasons = [f"Semantic similarity {best.dense:.2f} on {best.chunk.field.replace('_', ' ')}"]
            if best.rerank is not None:
                reasons.append(f"Reranker relevance {best.rerank:.2f}")
            overlap = sorted(q_tokens & {t for s in lst for t in self.index.tokens(s.chunk.id)})
            if overlap:
                reasons.append("Keyword overlap: " + ", ".join(overlap[:6]))
            bonus = 0.0
            if cfg.fingerprint and fp and base >= 0.3:
                bonus, fp_reasons = fingerprint_bonus(r, fp)
                reasons += fp_reasons
            if r.source == "learning":
                bonus += 0.03
                reasons.append("Verified learning written back by an engineer")
            if r.success_count:
                bonus += 0.02 * min(r.success_count, 3)
                reasons.append(f"Fix confirmed {r.success_count}x by engineers")
            # Metadata bonuses matter most for mid-range matches and cannot push weak matches over the top.
            score = base + min(bonus, 0.25) * min(1.0, 2 * (1 - base))
            conf = int(round(100 * min(1.0, score)))
            evidence = [
                Evidence(chunk_id=s.chunk.id, field=s.chunk.field, text=_strip_header(s.chunk.text)[:400],
                         score=round(s.rel, 3))
                for s in lst[:2]
            ]
            matches.append(to_match(r, conf, reasons, evidence, score))
        matches.sort(key=lambda m: m.score, reverse=True)
        if group:
            matches = self.group_duplicates(matches)
        return matches[:top_k]

    # ---------- reworded duplicates ----------
    def signature(self, record_id: str) -> np.ndarray | None:
        for field in ("root_cause", "symptom", "change"):
            cid = f"{record_id}#{field}"
            if cid in self.index.vecs:
                return self.index.vecs[cid]
        return None

    def group_duplicates(self, matches: list[Match]) -> list[Match]:
        groups: list[Match] = []
        sigs: list[np.ndarray | None] = []
        for m in matches:
            v = self.signature(m.record_id)
            for g, gv in zip(groups, sigs):
                if v is not None and gv is not None and g.node_type == m.node_type and float(v @ gv) >= self.dup_sim:
                    g.duplicates.append(DuplicateRef(record_id=m.record_id, confidence=m.confidence, node=m.node, date=m.date))
                    break
            else:
                groups.append(m)
                sigs.append(v)
        return groups

    def clusters(self) -> list[list[LNIRecord]]:
        """Group all problem records into recurring-issue clusters (repeat-failure trend view)."""
        recs = sorted((r for r in self.records.values() if r.is_problem), key=lambda r: r.date)
        clusters: list[list[LNIRecord]] = []
        sigs: list[np.ndarray | None] = []
        for r in recs:
            v = self.signature(r.id)
            for c, cv in zip(clusters, sigs):
                if v is not None and cv is not None and c[0].node_type == r.node_type and float(v @ cv) >= self.dup_sim:
                    c.append(r)
                    break
            else:
                clusters.append([r])
                sigs.append(v)
        return sorted(clusters, key=len, reverse=True)

    # ---------- MOP step linkage ----------
    def mop_step_matches(self, mop: MopDoc, step: MopStep, max_per_step: int = 2) -> list[Match]:
        qvec = self.embedder.query(f"{mop.title}: {step.text}")
        out = []
        for r in self.records.values():
            if not r.is_problem:
                continue
            same_mop = bool(r.mop_id) and r.mop_id == mop.mop_id
            if not same_mop and r.node_type.lower() != mop.node_type.lower():
                continue
            ids = [c for c in self.index.by_record.get(r.id, []) if not c.endswith(("#details", "#resolution"))]
            if not ids:
                continue
            best = max(self.index.sim(qvec, c) for c in ids)
            s = cos_scaled(best)
            if same_mop and r.mop_step == str(step.no):
                conf, why = int(round(100 * min(1.0, 0.72 + 0.25 * s))), f"Recorded as failing at {mop.mop_id} step {step.no}"
            elif same_mop and s >= 0.72:
                conf, why = int(round(100 * 0.85 * s)), f"Same MOP; similar to step text ({best:.2f})"
            elif s >= 0.8:
                conf, why = int(round(100 * 0.75 * s)), f"Same node type; similar to step text ({best:.2f})"
            else:
                continue
            out.append(to_match(r, conf, [why], []))
        out.sort(key=lambda m: m.score, reverse=True)
        return out[:max_per_step]


def fingerprint_bonus(r: LNIRecord, fp: Fingerprint) -> tuple[float, list[str]]:
    b, why = 0.0, []
    low = lambda xs: {x.lower() for x in xs}  # noqa: E731
    if r.node and r.node.lower() in low(fp.nodes):
        b += 0.04
        why.append(f"Same node {r.node}")
    if r.node_type and r.node_type.lower() in low(fp.node_types):
        b += 0.06
        why.append(f"Same node type ({r.node_type})")
    if r.vendor and r.vendor.lower() in low(fp.vendors):
        b += 0.02
    if r.release and r.release in fp.releases:
        b += 0.03
        why.append(f"Same release {r.release}")
    if r.mop_id and r.mop_id in fp.mop_ids:
        b += 0.08
        why.append(f"Same MOP {r.mop_id}" + (f" step {r.mop_step}" if r.mop_step else ""))
    hay = (r.error_signature + " " + r.symptoms).lower()
    hits = [e for e in fp.error_signatures if len(e) > 3 and e.lower() in hay]
    if hits:
        b += 0.06
        why.append("Error signature match: " + ", ".join(hits[:3]))
    return min(b, 0.2), why


def to_match(r: LNIRecord, conf: int, reasons: list[str], evidence: list[Evidence],
             score: float | None = None) -> Match:
    return Match(
        record_id=r.id, title=r.title, confidence=conf, score=round(conf / 100 if score is None else score, 4),
        node=r.node, node_type=r.node_type, vendor=r.vendor,
        release=r.release, mop_id=r.mop_id, mop_step=r.mop_step, date=r.date, outcome=r.outcome,
        severity=r.severity, root_cause=r.root_cause, resolution=r.resolution, learning=r.learning,
        verified=r.verified, source=r.source, success_count=r.success_count, reasons=reasons, evidence=evidence,
    )
