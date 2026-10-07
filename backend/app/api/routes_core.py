from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..agent.learning import write_learning
from ..config import settings
from ..schemas import (FeedbackRequest, FeedbackResponse, IngestRequest, IngestResponse, LNIRecord, MatchRequest,
                       MatchResponse, MopDoc, Recommendation, RecommendRequest)
from ..services import get_agent, get_kb

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, tags=["core"],
             summary="Ingest LNI history (a folder, or raw records) and rebuild the index")
def ingest(req: IngestRequest) -> IngestResponse:
    kb = get_kb()
    try:
        return kb.ingest(path=req.path, raw_records=req.records, reset=req.reset)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/match", response_model=MatchResponse, tags=["core"],
             summary="Fingerprint + hybrid search with reranking. Returns ranked past LNIs with confidence (no LLM)")
def match(req: MatchRequest) -> MatchResponse:
    kb = get_kb()
    f = req.filters
    fp = kb.fingerprinter.extract(req.text, f.node, f.release, f.mop_id)
    matches = kb.searcher.match_records(req.text, flt=f.as_meta(), fp=fp, top_k=req.top_k)
    threshold = settings.match_threshold
    return MatchResponse(fingerprint=fp, matches=matches, threshold=threshold,
                         no_match=not matches or matches[0].confidence < threshold)


@router.post("/recommend", response_model=Recommendation, tags=["core"],
             summary="Run the agent: plan searches, call tools, rank, draft cited advice, check citations")
def recommend(req: RecommendRequest) -> Recommendation:
    return get_agent().run_sync(req)


@router.post("/recommend/stream", tags=["core"],
             summary="Same as /recommend, streamed as Server-Sent Events (agent trace + LLM tokens + final result)")
def recommend_stream(req: RecommendRequest) -> StreamingResponse:
    def events():
        for ev in get_agent().run(req):
            yield f"event: {ev.type}\ndata: {json.dumps(ev.model_dump(), default=str)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/feedback", response_model=FeedbackResponse, tags=["core"],
             summary="Write back a verified learning (engineer-confirmed) to the knowledge base and ticket")
def feedback(req: FeedbackRequest) -> FeedbackResponse:
    try:
        return write_learning(get_kb(), req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/health", tags=["info"])
def health() -> dict[str, Any]:
    kb, agent = get_kb(), get_agent()
    return {
        "status": "ok" if kb.ready else "starting",
        "llm": {"enabled": settings.llm_enabled, "model": settings.llm_model, "base_url": settings.llm_base_url,
                "available": agent.llm.available()},
        "embed_model": kb.embedder.name,
        "reranker": kb.reranker.name if kb.reranker else None,
        "vector_store": kb.index.store.name,
        "threshold": settings.match_threshold,
        **kb.stats(),
    }


@router.get("/stats", tags=["info"])
def stats() -> dict[str, int]:
    return get_kb().stats()


@router.get("/cases", response_model=list[LNIRecord], tags=["knowledge"])
def cases(q: str | None = None, node_type: str | None = None, source: str | None = None,
          problems_only: bool = False, limit: int = Query(200, le=1000)) -> list[LNIRecord]:
    recs = sorted(get_kb().records.values(), key=lambda r: r.date, reverse=True)
    if node_type:
        recs = [r for r in recs if r.node_type.lower() == node_type.lower()]
    if source:
        recs = [r for r in recs if r.source == source]
    if problems_only:
        recs = [r for r in recs if r.is_problem]
    if q:
        ql = q.lower()
        recs = [r for r in recs if ql in r.model_dump_json().lower()]
    return recs[:limit]


@router.get("/cases/{record_id}", response_model=LNIRecord, tags=["knowledge"])
def case(record_id: str) -> LNIRecord:
    r = get_kb().records.get(record_id)
    if not r:
        raise HTTPException(404, f"{record_id} not found")
    return r


@router.get("/mops", response_model=list[MopDoc], tags=["knowledge"])
def mops() -> list[MopDoc]:
    return list(get_kb().mops.values())


@router.get("/nodes", tags=["knowledge"])
def nodes() -> list[dict[str, str]]:
    info = get_kb().fingerprinter.node_info
    return [{"node": n, "node_type": t, "vendor": v} for n, (t, v) in sorted(info.items())]


@router.get("/tools", tags=["info"], summary="The agent's tool registry (JSON schemas)")
def tools() -> list[dict[str, Any]]:
    return get_agent().tools.describe()


@router.get("/trends", tags=["insights"], summary="Repeat-failure trends: recurring problems, by node type / outcome / month")
def trends() -> dict[str, Any]:
    kb = get_kb()
    problems = [r for r in kb.records.values() if r.is_problem]
    recurring = []
    for c in kb.searcher.clusters():
        if len(c) < 2:
            continue
        recurring.append({
            "title": c[-1].title, "root_cause": c[-1].root_cause, "count": len(c), "node_type": c[0].node_type,
            "nodes": sorted({r.node for r in c if r.node}), "ids": [r.id for r in c],
            "first_seen": c[0].date, "last_seen": c[-1].date,
            "outcomes": dict(Counter(r.outcome for r in c if r.outcome)),
        })
    return {
        "recurring": recurring,
        "by_node_type": dict(Counter(r.node_type for r in problems).most_common()),
        "by_outcome": dict(Counter(r.outcome for r in problems).most_common()),
        "by_month": dict(sorted(Counter(r.date[:7] for r in problems if r.date).items())),
        "problem_records": len(problems),
        "total_records": len(kb.records),
    }


@router.get("/digest", tags=["insights"], summary="Digest of the top recurring issues (weekly digest, as Markdown)")
def digest(days: int = 30, top: int = 5) -> dict[str, Any]:
    kb = get_kb()
    dates = [r.date for r in kb.records.values() if r.date]
    end = max(dates) if dates else date.today().isoformat()
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    lines = [f"# LNI digest {start} .. {end}", ""]
    rows = []
    for c in kb.searcher.clusters():
        recent = [r for r in c if r.date >= start]
        if recent:
            rows.append((len(recent), len(c), c))
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for i, (n_recent, n_all, c) in enumerate(rows[:top], 1):
        last = c[-1]
        lines.append(f"{i}. **{last.title}** - {n_recent} in period, {n_all} total ({last.node_type}). "
                     f"Learning: {last.learning or '-'} [{', '.join(r.id for r in c)}]")
    if not rows:
        lines.append("No problem LNIs in this period.")
    return {"start": start, "end": end, "markdown": "\n".join(lines)}


@router.get("/notifications", tags=["integration"])
def notifications(limit: int = 20) -> list[dict[str, Any]]:
    return get_kb().store.notifications(limit)
