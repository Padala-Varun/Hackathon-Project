"""Tools the agent can call. Each has a JSON schema (so an LLM tool-calling loop could drive them too).
Side-effecting tools are blocked unless explicitly allowed: the agent is read-only by design."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import httpx

from ..rag.search import to_match
from ..schemas import Fingerprint, Match, MopDoc, MopStepAdvice, RecItem

if TYPE_CHECKING:
    from ..services import KnowledgeBase


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    side_effect: bool = False


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def call(self, name: str, allow_side_effects: bool = False, **kwargs: Any) -> Any:
        tool = self.tools[name]
        if tool.side_effect and not allow_side_effects:
            raise PermissionError(f"Tool '{name}' has side effects and is not allowed in the agent loop")
        return tool.fn(**kwargs)

    def describe(self) -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "parameters": t.parameters,
                 "side_effect": t.side_effect} for t in self.tools.values()]


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


def build_tools(kb: "KnowledgeBase", webhook_url: str, threshold: int) -> ToolRegistry:
    reg = ToolRegistry()

    def search_by_symptom(text: str, node_type: str | None = None, fields: list[str] | None = None,
                          fp: Fingerprint | None = None, top_k: int = 8) -> list[Match]:
        flt = {"node_type": node_type} if node_type else None
        return kb.searcher.match_records(text, flt=flt, fp=fp, top_k=top_k, fields=fields, group=False)

    def search_by_mop_step(mop_id: str) -> list[MopStepAdvice]:
        mop: MopDoc | None = kb.mops.get(mop_id)
        if not mop:
            return []
        out = []
        for step in mop.steps:
            warnings: dict[str, RecItem] = {}
            for m in kb.searcher.mop_step_matches(mop, step):
                if m.confidence < threshold:
                    continue
                text = m.learning or m.root_cause
                if text in warnings:  # reworded duplicates with the same learning -> one warning, both cited
                    warnings[text].citations.append(m.record_id)
                else:
                    warnings[text] = RecItem(kind="pitfall", text=text, citations=[m.record_id], confidence=m.confidence)
            out.append(MopStepAdvice(no=step.no, text=step.text, warnings=list(warnings.values())))
        return out

    def search_by_fingerprint(node_type: str, release: str, top_k: int = 5) -> list[Match]:
        """Known issues recorded for the same product AND release (the deck's 'fingerprint matching')."""
        def same_release(r: str) -> bool:
            return bool(r) and (r == release or r.startswith(release + ".") or release.startswith(r + "."))
        hits = [r for r in kb.records.values()
                if r.is_problem and r.node_type.lower() == node_type.lower() and same_release(r.release)]
        hits.sort(key=lambda r: r.date, reverse=True)
        return [to_match(r, 62, [f"Fingerprint match: known issue recorded for {r.node_type} release {r.release}"], [])
                for r in hits[:top_k]]

    def node_history(node: str, limit: int = 10) -> list[dict[str, Any]]:
        recs = sorted((r for r in kb.records.values() if r.node.upper() == node.upper()), key=lambda r: r.date,
                      reverse=True)
        return [{"id": r.id, "date": r.date, "title": r.title, "change_type": r.change_type, "outcome": r.outcome,
                 "root_cause": r.root_cause} for r in recs[:limit]]

    def get_mop(mop_id: str) -> dict[str, Any] | None:
        mop = kb.mops.get(mop_id)
        return mop.model_dump() if mop else None

    def get_ticket(ticket_id: str) -> dict[str, Any] | None:
        return kb.store.get("tickets", ticket_id)

    def notify_webhook(card: dict[str, Any]) -> dict[str, Any]:
        if webhook_url.startswith("local://"):
            return {"delivered": True, "target": "mock webhook (UI notifications)", **kb.store.add_notification(card)}
        try:
            r = httpx.post(webhook_url, json=card, timeout=5)
            kb.store.add_notification({**card, "delivered_to": webhook_url, "status_code": r.status_code})
            return {"delivered": r.is_success, "target": webhook_url, "status_code": r.status_code}
        except httpx.HTTPError as exc:
            return {"delivered": False, "target": webhook_url, "error": str(exc)}

    reg.register(Tool("search_by_symptom", "Hybrid search (semantic + keyword + metadata, reranked) over past LNIs.",
                      _obj({"text": {"type": "string"}, "node_type": {"type": "string"},
                            "fields": {"type": "array", "items": {"type": "string"}}}, ["text"]), search_by_symptom))
    reg.register(Tool("search_by_mop_step", "For each step of a MOP, find past LNIs that failed at or near that step.",
                      _obj({"mop_id": {"type": "string"}}, ["mop_id"]), search_by_mop_step))
    reg.register(Tool("search_by_fingerprint", "Known issues recorded for the same product and release.",
                      _obj({"node_type": {"type": "string"}, "release": {"type": "string"}}, ["node_type", "release"]),
                      search_by_fingerprint))
    reg.register(Tool("node_history", "List past LNIs executed on a node, newest first.",
                      _obj({"node": {"type": "string"}}, ["node"]), node_history))
    reg.register(Tool("get_mop", "Read a MOP and its steps.", _obj({"mop_id": {"type": "string"}}, ["mop_id"]), get_mop))
    reg.register(Tool("get_ticket", "Read an incident/change ticket from the ticketing API.",
                      _obj({"ticket_id": {"type": "string"}}, ["ticket_id"]), get_ticket))
    reg.register(Tool("notify_webhook", "Send a Teams-style card for high-risk planned LNIs.",
                      _obj({"card": {"type": "object"}}, ["card"]), notify_webhook, side_effect=True))
    reg.register(Tool("write_learning", "Write a verified learning back to the knowledge base and ticket. "
                      "Only callable from POST /feedback after an engineer confirms.",
                      _obj({"feedback": {"type": "object"}}, ["feedback"]), lambda **_: None, side_effect=True))
    return reg
