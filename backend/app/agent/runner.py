"""The agent loop: fingerprint -> clarify? -> plan -> tool calls -> re-query if weak -> rank -> cited draft
-> (LLM rewrite) -> citation check -> risk score -> notify. Every step is emitted as an AgentEvent."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from ..config import Settings
from ..glossary import GENERAL_PRECHECKS
from ..rag.search import to_match
from ..schemas import (AgentEvent, Fingerprint, Match, MopStepAdvice, RecItem, Recommendation, RecommendRequest,
                       Risk)
from . import guardrails
from .llm import LLMClient
from .planner import PlanStep, make_plan, requery_steps
from .prompts import build_messages
from .tools import build_tools

if TYPE_CHECKING:
    from ..services import KnowledgeBase

SEVERITY_W = {"critical": 1.0, "high": 1.0, "medium": 0.6, "low": 0.3}
OUTCOME_W = {"outage": 1.0, "rollback": 0.9, "service degraded": 0.75, "degraded": 0.75, "resolved": 0.45}


def describe_fp(fp: Fingerprint) -> str:
    parts = [
        ("node", fp.nodes), ("node type", fp.node_types), ("vendor", fp.vendors), ("release", fp.releases),
        ("MOP", fp.mop_ids), ("change", fp.change_types), ("errors", fp.error_signatures[:3]),
        ("commands", fp.commands[:2]),
    ]
    shown = [f"{k}: {', '.join(map(str, v))}" for k, v in parts if v]
    return "Fingerprint - " + ("; ".join(shown) if shown else "no technical identifiers found")


class Agent:
    def __init__(self, kb: "KnowledgeBase", settings: Settings, llm: LLMClient):
        self.kb, self.s, self.llm = kb, settings, llm
        self.tools = build_tools(kb, settings.webhook_url, settings.match_threshold)

    # ---------- public ----------
    def run_sync(self, req: RecommendRequest) -> Recommendation:
        final = None
        for ev in self.run(req):
            if ev.type == "final":
                final = ev.data["recommendation"]
        return Recommendation(**final)

    def run(self, req: RecommendRequest) -> Iterator[AgentEvent]:
        trace: list[AgentEvent] = []

        def ev(type_: str, message: str = "", **data: Any) -> AgentEvent:
            e = AgentEvent(type=type_, message=message, data=data)
            if type_ != "llm_token":
                trace.append(e)
            return e

        threshold = self.s.match_threshold
        fp = self.kb.fingerprinter.extract(req.text, req.node, req.release, req.mop_id)
        yield ev("fingerprint", describe_fp(fp), fingerprint=fp.model_dump())

        clar = guardrails.clarification_needed(req.mode, fp, req, self.kb)
        if clar and req.mode == "incident":  # don't block an incident: search now, offer the refinement
            yield ev("clarify", clar.question + " (searching anyway; answer to refine)", clarification=clar.model_dump())
        elif clar:
            yield ev("clarify", clar.question, clarification=clar.model_dump())
            rec = Recommendation(status="needs_clarification", mode=req.mode, fingerprint=fp, clarification=clar,
                                 trace=trace)
            yield ev("final", "Waiting for the engineer's answer", recommendation=rec.model_dump())
            return

        mop = self.kb.mops.get(fp.mop_ids[0]) if fp.mop_ids else None
        plan = make_plan(req.mode, fp, req.text, mop.title if mop else "")
        yield ev("plan", f"Planned {len(plan)} tool call(s)", steps=[p.describe() for p in plan])

        merged: dict[str, Match] = {}
        state: dict[str, Any] = {"history": [], "mop_steps": [], "done": set()}
        for step in plan:
            yield from self._execute(step, fp, merged, state, ev)

        best = max((m.confidence for m in merged.values()), default=0)
        for round_no in (1, 2):
            if best >= threshold:
                break
            strategy, steps = requery_steps(round_no, fp, req.text)
            yield ev("requery", f"Best confidence {best}% is below the {threshold}% threshold - {strategy}",
                     round=round_no)
            for step in steps:
                yield from self._execute(step, fp, merged, state, ev)
            best = max((m.confidence for m in merged.values()), default=0)

        ranked = sorted(merged.values(), key=lambda m: (m.confidence, m.score), reverse=True)
        grouped = self.kb.searcher.group_duplicates([m.model_copy(update={"duplicates": []}) for m in ranked])
        verified = [m for m in grouped if m.confidence >= threshold][: req.top_k]
        weak = [m for m in grouped if m.confidence < threshold][:3]
        yield ev("rank", f"{len(verified)} verified match(es) at or above {threshold}% confidence"
                 + (f"; {len(weak)} weaker candidate(s) not used as evidence" if weak else ""),
                 matches=[{"id": m.record_id, "confidence": m.confidence,
                           "duplicates": [d.record_id for d in m.duplicates]} for m in verified])

        mop_steps: list[MopStepAdvice] = state["mop_steps"]
        rec = Recommendation(status="ok", mode=req.mode, fingerprint=fp, matches=verified, clarification=clar,
                             node_history=state["history"], mop_id=mop.mop_id if mop else "", mop_steps=mop_steps)

        if not verified:
            rec.status = "no_match"
            rec.matches = weak
            rec.summary = (f"{guardrails.NO_MATCH} in the LNI history for this {req.mode.replace('_', '-')}. "
                           "Nothing is suggested as a fix; escalate per the normal process.")
            if req.mode == "pre_change":
                rec.prechecks = [RecItem(kind="general", text=t, citations=[]) for t in GENERAL_PRECHECKS]
            yield ev("verify", "No record cleared the confidence threshold - refusing to guess a fix")
            rec.trace = trace
            yield ev("final", rec.summary, recommendation=rec.model_dump())
            return

        rec.items, rec.prechecks = self._build_items(req.mode, verified)
        if req.mode == "pre_change":
            rec.risk = self._risk(verified, state["history"], mop_steps)
            yield ev("risk", f"Pre-change risk {rec.risk.score}/100 ({rec.risk.level})", risk=rec.risk.model_dump())

        draft = "\n".join(f"- {i.text} [{', '.join(i.citations)}]" for i in rec.items + rec.prechecks[:3])
        allowed = {i for m in verified for i in m.all_ids} | {c for s in mop_steps for w in s.warnings for c in w.citations}
        if mop:
            allowed.add(mop.mop_id)
        pattern = guardrails.id_pattern(list(self.kb.records))
        rec.summary = draft
        yield ev("draft", f"Drafted {len(rec.items) + len(rec.prechecks)} cited statements from the verified records")

        if req.use_llm and self.llm.available():
            yield ev("llm_start", f"Asking {self.s.llm_model} to rewrite the draft using only the cited evidence")
            text = ""
            try:
                for tok in self.llm.stream(build_messages(req.mode, req.text, verified, draft)):
                    text += tok
                    yield ev("llm_token", tok)
            except Exception as exc:  # timeouts, connection loss
                yield ev("llm_error", f"LLM failed ({exc}); keeping the deterministic draft")
            kept, dropped = guardrails.verify_citations(text, allowed, pattern)
            rec.dropped_claims = dropped
            if kept and not kept[0].lower().lstrip("-* ").startswith(guardrails.NO_MATCH.lower()):
                rec.summary, rec.llm_used = "\n".join(kept), True
            yield ev("verify", f"Citation check on LLM output: kept {len(kept)}, dropped {len(dropped)} uncited/unknown"
                     + ("" if rec.llm_used else " - using the deterministic draft"), dropped=dropped)
        else:
            kept, _ = guardrails.verify_citations(draft, allowed, pattern)
            yield ev("llm_skipped", "LLM not reachable or disabled - using the deterministic cited draft")
            yield ev("verify", f"Citation check: {len(kept)} statements, each cites a verified record")

        if rec.risk and rec.risk.level == "High" and req.notify:
            card = self._card(req, fp, rec)
            result = self.tools.call("notify_webhook", allow_side_effects=True, card=card)
            rec.notification = {"card": card, "result": result}
            yield ev("notify", f"High-risk LNI: notification sent to {result.get('target')}", result=result)

        rec.trace = trace
        yield ev("final", "Recommendation ready - the engineer reviews and decides", recommendation=rec.model_dump())

    # ---------- internals ----------
    def _execute(self, step: PlanStep, fp: Fingerprint, merged: dict[str, Match], state: dict[str, Any], ev):
        key = (step.tool, repr(sorted((k, v) for k, v in step.args.items() if v is not None)))
        if key in state["done"]:
            yield ev("tool_skip", f"Skipped {step.tool}: identical search already run", tool=step.tool)
            return
        state["done"].add(key)
        yield ev("tool_call", step.label(), tool=step.tool, reason=step.reason)
        args = dict(step.args)
        if step.tool == "search_by_symptom":
            args["fp"] = fp
        out = self.tools.call(step.tool, **{k: v for k, v in args.items() if v is not None})
        if step.tool == "node_history":
            state["history"] = out
            bad = [h for h in out if h["outcome"].lower() in ("outage", "rollback")]
            yield ev("tool_result", f"{len(out)} past LNI(s) on {step.args['node']}; {len(bad)} ended in rollback/outage",
                     items=out[:5])
        elif step.tool == "search_by_mop_step":
            state["mop_steps"] = out
            for s in out:
                for w in s.warnings:
                    for rid in w.citations:
                        if rid not in merged or merged[rid].confidence < (w.confidence or 0):
                            merged[rid] = to_match(self.kb.records[rid], w.confidence or 0,
                                                   [f"Linked to {step.args['mop_id']} step {s.no}"], [])
            flagged = [s.no for s in out if s.warnings]
            yield ev("tool_result", f"{len(out)} MOP steps checked; known pitfalls at step(s) {flagged or 'none'}",
                     flagged_steps=flagged)
        else:
            for m in out:
                cur = merged.get(m.record_id)
                if not cur or (m.confidence, m.score) > (cur.confidence, cur.score):
                    if cur:
                        m.reasons = list(dict.fromkeys(m.reasons + cur.reasons))
                    merged[m.record_id] = m
            top = f" (top: {out[0].record_id} {out[0].confidence}%)" if out else ""
            yield ev("tool_result", f"{len(out)} candidate(s){top}",
                     results=[{"id": m.record_id, "confidence": m.confidence} for m in out[:5]])

    def _build_items(self, mode: str, matches: list[Match]) -> tuple[list[RecItem], list[RecItem]]:
        items: list[RecItem] = []
        pre: list[RecItem] = []
        if mode == "incident":
            top = matches[0]
            seen = f", seen {len(top.all_ids)}x" if top.duplicates else ""
            items.append(RecItem(kind="cause", text=f"Most likely root cause ({top.confidence}% match{seen}): "
                                 f"{top.root_cause}", citations=top.all_ids, confidence=top.confidence))
            if top.resolution:
                items.append(RecItem(kind="fix", text=f"Fix that worked: {top.resolution}", citations=top.all_ids,
                                     confidence=top.confidence))
            for m in matches[1:3]:
                if m.confidence >= top.confidence - 20:
                    items.append(RecItem(kind="alternative", text=f"Also consider ({m.confidence}% match): {m.root_cause}",
                                         citations=m.all_ids, confidence=m.confidence))
        else:
            for m in matches[:5]:
                where = f"{m.outcome or 'issue'} on {m.node or m.node_type}, {m.date}"
                items.append(RecItem(kind="pitfall", text=f"Known pitfall ({where}): {m.root_cause}",
                                     citations=m.all_ids, confidence=m.confidence))
        texts: set[str] = set()
        for m in matches[:5]:
            learnings = [m.learning] + [self.kb.records[d.record_id].learning for d in m.duplicates
                                        if d.record_id in self.kb.records]
            for text in learnings:
                if text and text not in texts:
                    texts.add(text)
                    pre.append(RecItem(kind="precheck", text=text, citations=m.all_ids, confidence=m.confidence))
        return items, pre

    def _risk(self, matches: list[Match], history: list[dict[str, Any]], mop_steps: list[MopStepAdvice]) -> Risk:
        p_safe, reasons = 1.0, []
        for m in matches:
            w = (m.confidence / 100) * SEVERITY_W.get(m.severity.lower(), 0.5) * OUTCOME_W.get(m.outcome.lower(), 0.5)
            w *= 1 + 0.15 * len(m.duplicates)
            p_safe *= 1 - min(0.9, 0.6 * w)
            seen = f", seen {len(m.all_ids)}x" if m.duplicates else ""
            reasons.append(f"{m.record_id}: {m.outcome or 'issue'} ({m.severity or 'n/a'} severity), "
                           f"{m.confidence}% match{seen}")
        bad = [h for h in history if h["outcome"].lower() in ("outage", "rollback")]
        if bad:
            p_safe *= 0.85
            reasons.append(f"Node history: {len(bad)} past LNI(s) on this node ended in rollback/outage")
        flagged = [s.no for s in mop_steps if s.warnings]
        if flagged:
            reasons.append(f"MOP steps with known pitfalls: {', '.join(map(str, flagged))}")
        score = int(round(100 * (1 - p_safe)))
        level = "High" if score >= self.s.high_risk_threshold else "Medium" if score >= 40 else "Low"
        return Risk(score=score, level=level, reasons=reasons)

    @staticmethod
    def _card(req: RecommendRequest, fp: Fingerprint, rec: Recommendation) -> dict[str, Any]:
        top = rec.items[0] if rec.items else None
        return {
            "@type": "MessageCard", "@context": "http://schema.org/extensions", "themeColor": "D9534F",
            "summary": "High-risk planned LNI",
            "title": f"High-risk planned LNI ({rec.risk.score}/100): {req.text[:90]}",
            "sections": [{
                "facts": [
                    {"name": "Node", "value": ", ".join(fp.nodes) or "-"},
                    {"name": "MOP", "value": ", ".join(fp.mop_ids) or "-"},
                    {"name": "Release", "value": ", ".join(fp.releases) or "-"},
                    {"name": "Top pitfall", "value": f"{top.text[:200]} [{', '.join(top.citations)}]" if top else "-"},
                ],
                "text": "Review the cited past LNIs and pre-checks before executing. The agent does not execute changes.",
            }],
        }
