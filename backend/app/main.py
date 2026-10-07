"""LNI Learning & Prevention Agent - FastAPI app. Run: uvicorn app.main:app --port 8000 (from backend/)."""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_core, routes_mock
from .config import settings
from .services import init_services

DESCRIPTION = """
Institutional memory for every Live Network Intervention (LNI).

* **BEFORE** a planned LNI - `POST /recommend` with `mode=pre_change`: known pitfalls, validation steps, risk score.
* **DURING** an incident - `POST /match` (search only) or `POST /recommend` with `mode=incident`.
* **AFTER** resolution - `POST /feedback` writes the engineer-verified learning back.

The agent is read-only: it surfaces cited history; the engineer decides.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    _, agent = init_services(settings)
    threading.Thread(target=agent.llm.warm_up, daemon=True).start()
    yield


app = FastAPI(title="LNI Learning & Prevention Agent", version="1.0.0", description=DESCRIPTION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(routes_core.router)
app.include_router(routes_mock.router)
