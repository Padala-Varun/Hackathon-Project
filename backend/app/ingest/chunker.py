"""Chunk BY FIELD so every answer can cite the exact part of a record (root cause, resolution, MOP step...)."""
from __future__ import annotations

from ..schemas import Chunk, LNIRecord, LogSnippet, MopDoc
from ..textutil import join


def _header(r: LNIRecord) -> str:
    parts = [r.node_type, r.vendor, f"rel {r.release}" if r.release else "", r.node]
    parts = [p for p in parts if p]
    return f"[{' | '.join(parts)}] " if parts else ""


def record_chunks(r: LNIRecord) -> list[Chunk]:
    meta = {
        "record_id": r.id, "kind": "lni", "node": r.node, "node_type": r.node_type, "vendor": r.vendor,
        "release": r.release, "mop_id": r.mop_id, "mop_step": r.mop_step, "verified": r.verified,
        "source": r.source, "date": r.date,
    }
    mop_ref = f"MOP {r.mop_id} step {r.mop_step}" if r.mop_id and r.mop_step else (f"MOP {r.mop_id}" if r.mop_id else "")
    has_symptoms = bool(r.symptoms or r.error_signature)
    fields = {
        "symptom": join(r.title, r.symptoms, r.error_signature) if has_symptoms else "",
        # only a real description of the change (a bare phase word like "Integration" would just be noise)
        "change": join(r.change_type, "" if has_symptoms else r.title, r.description, mop_ref)
        if (r.description or mop_ref or not has_symptoms) else "",
        "root_cause": r.root_cause,
        "resolution": join(r.resolution, r.commands),
        "learning": r.learning,
        "details": "; ".join(f"{k}: {v}" for k, v in r.extra.items()),
    }
    head = _header(r)
    return [
        Chunk(id=f"{r.id}#{f}", record_id=r.id, kind="lni", field=f, text=head + text, meta={**meta, "field": f})
        for f, text in fields.items()
        if text.strip()
    ]


def mop_chunks(m: MopDoc) -> list[Chunk]:
    return [
        Chunk(
            id=f"{m.mop_id}#step{s.no}", record_id=m.mop_id, kind="mop", field="mop_step",
            text=f"[{m.node_type}] {m.mop_id} {m.title} - step {s.no}: {s.text}",
            meta={"record_id": m.mop_id, "kind": "mop", "field": "mop_step", "mop_id": m.mop_id,
                  "mop_step": str(s.no), "node_type": m.node_type, "vendor": m.vendor},
        )
        for s in m.steps
    ]


def log_chunks(log: LogSnippet) -> list[Chunk]:
    return [
        Chunk(
            id=f"{log.id}#log", record_id=log.id, kind="log", field="log", text=log.text[:2500],
            meta={"record_id": log.id, "kind": "log", "field": "log", "node": log.node,
                  "related": ",".join(log.related_ids)},
        )
    ]
