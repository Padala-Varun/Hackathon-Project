"""Mock integrations: a ticketing API (read incidents, write learnings), node history and a webhook receiver."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import get_agent, get_kb

router = APIRouter(tags=["mock integrations"])


class TicketLearning(BaseModel):
    author: str
    text: str


@router.get("/tickets", summary="Mock ticketing API: list tickets")
def list_tickets(status: str | None = None) -> list[dict[str, Any]]:
    rows = get_kb().store.all("tickets")
    return [t for t in rows if not status or t.get("status", "").lower() == status.lower()]


@router.get("/tickets/{ticket_id}", summary="Mock ticketing API: read one ticket")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    t = get_kb().store.get("tickets", ticket_id)
    if not t:
        raise HTTPException(404, f"{ticket_id} not found")
    return t


@router.post("/tickets/{ticket_id}/learnings", summary="Mock ticketing API: append a learning note to a ticket")
def add_ticket_learning(ticket_id: str, body: TicketLearning) -> dict[str, Any]:
    kb = get_kb()
    t = kb.store.get("tickets", ticket_id)
    if not t:
        raise HTTPException(404, f"{ticket_id} not found")
    t.setdefault("learnings", []).append({"by": body.author, "date": date.today().isoformat(), "note": body.text})
    kb.store.upsert("tickets", ticket_id, t, t.get("type", ""))
    return t


@router.get("/nodes/{node}/history", summary="Node history lookup: past LNIs on a node")
def node_history(node: str) -> list[dict[str, Any]]:
    return get_agent().tools.call("node_history", node=node)


@router.post("/mock/webhook", summary="Mock Teams/email webhook receiver (stores the card for the UI)")
def mock_webhook(card: dict[str, Any]) -> dict[str, Any]:
    return get_kb().store.add_notification(card)
