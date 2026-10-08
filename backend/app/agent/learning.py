"""AFTER resolution: write the engineer-verified learning back to the knowledge base and the ticket."""
from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from ..schemas import FeedbackRequest, FeedbackResponse, LNIRecord

if TYPE_CHECKING:
    from ..services import KnowledgeBase


def _family(components: str) -> str:
    """'CMG-a2, CMG' -> 'CMG' (product family used as node type, like the official tickets)."""
    m = re.match(r"\s*([A-Za-z]+)", components or "")
    return m.group(1).upper() if m else ""


def write_learning(kb: "KnowledgeBase", req: FeedbackRequest) -> FeedbackResponse:
    if not req.verified_by.strip():
        raise ValueError("verified_by is required: a human must validate every learning")
    has_content = bool(req.verified_root_cause.strip() or req.verified_fix.strip())
    if not has_content and not (req.worked and req.matched_ids):
        raise ValueError("Provide a verified root cause/fix, or confirm (worked=true) at least one matched record")
    if has_content:
        missing = [name for name, v in (("Components", req.components), ("Build", req.build),
                                        ("RCA category", req.rca_category)) if not v.strip()]
        if missing:
            raise ValueError(f"Required for a new lesson: {', '.join(missing)}")

    now = datetime.now().astimezone()  # local time with UTC offset, e.g. 2026-10-09T01:40:12+05:30
    stamp = now.isoformat(timespec="seconds")
    confirmed = []
    if req.worked:
        for rid in req.matched_ids:
            r = kb.records.get(rid)
            if r:
                kb.save_record(r.model_copy(update={"success_count": r.success_count + 1}))
                confirmed.append(rid)

    record = None
    if has_content:
        fp = kb.fingerprinter.extract(req.incident_text, req.node or None, req.release or None, req.mop_id or None)
        base = kb.records.get(req.matched_ids[0]) if req.matched_ids else None
        first = lambda xs, fallback="": xs[0] if xs else fallback  # noqa: E731
        record = LNIRecord(
            id=kb.next_learning_id(),
            title=req.title.strip() or req.incident_text.strip()[:100],
            date=now.date().isoformat(),
            change_type=base.change_type if base else "",
            vendor=req.vendor or first(fp.vendors, base.vendor if base else ""),
            node=(req.node or first(fp.nodes)).upper(),
            node_type=req.node_type or _family(req.components) or first(fp.node_types, base.node_type if base else ""),
            release=req.release or first(fp.releases),
            mop_id=(req.mop_id or first(fp.mop_ids)).upper(),
            symptoms=req.incident_text.strip(),
            error_signature="; ".join(fp.error_signatures[:4]),
            commands="; ".join(fp.commands[:4]),
            root_cause=req.verified_root_cause.strip(),
            resolution=req.verified_fix.strip(),
            learning=req.learning.strip(),
            outcome="Resolved",
            severity=base.severity if base else "",
            verified=True,
            source="learning",
            verified_by=req.verified_by.strip(),
            verified_at=stamp,
            related_ids=req.matched_ids,
            extra={"Components": req.components.strip(), "Build": req.build.strip(),
                   "RCA category": req.rca_category.strip()},
        )
        kb.add_record(record)

    ticket = None
    if req.ticket_id:
        ticket = kb.store.get("tickets", req.ticket_id)
        if ticket:
            ticket.setdefault("learnings", []).append({
                "by": req.verified_by, "timestamp": stamp,
                "record_id": record.id if record else None, "confirmed_ids": confirmed,
                "root_cause": req.verified_root_cause, "fix": req.verified_fix,
            })
            ticket["status"] = "Resolved"
            kb.store.upsert("tickets", ticket["id"], ticket, ticket.get("type", ""))

    parts = []
    if record:
        parts.append(f"Verified learning {record.id} saved at {now:%Y-%m-%d %H:%M} and indexed - searchable immediately")
    if confirmed:
        parts.append(f"fix confirmed on {', '.join(confirmed)}")
    if ticket:
        parts.append(f"ticket {ticket['id']} updated")
    return FeedbackResponse(message="; ".join(parts) or "Nothing to save", record=record, confirmed_ids=confirmed,
                            ticket=ticket)
