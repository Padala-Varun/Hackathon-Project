"""Minimal OpenAI-compatible chat client. Works with Ollama (/v1), Mistral's API or an organiser endpoint."""
from __future__ import annotations

import json
import threading
import time
from typing import Iterator
from urllib.parse import urlparse

import httpx

from ..config import Settings


class LLMClient:
    def __init__(self, s: Settings):
        self.s = s
        self._checked = (0.0, False)
        self._refreshing = threading.Lock()

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.s.llm_api_key}"} if self.s.llm_api_key else {}

    def check(self) -> bool:
        """Blocking probe: is the endpoint up and does it serve the configured model?"""
        try:
            r = httpx.get(f"{self.s.llm_base_url}/models", headers=self._headers, timeout=2)
            ids = [m.get("id", "") for m in r.json().get("data", [])] if r.is_success else []
            ok = any(i == self.s.llm_model or i.split(":")[0] == self.s.llm_model for i in ids)
        except (httpx.HTTPError, ValueError):
            ok = False
        self._checked = (time.time(), ok)
        return ok

    def available(self) -> bool:
        """Non-blocking: returns the last known state and refreshes it in the background when stale."""
        if not self.s.llm_enabled:
            return False
        ts, ok = self._checked
        if time.time() - ts > 20 and not self._refreshing.locked():
            threading.Thread(target=self._refresh, daemon=True).start()
        return ok

    def _refresh(self) -> None:
        with self._refreshing:
            self.check()

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        body = {"model": self.s.llm_model, "messages": messages, "stream": True, "temperature": 0.1,
                "max_tokens": self.s.llm_max_tokens}
        timeout = httpx.Timeout(self.s.llm_timeout_s, connect=5)
        with httpx.stream("POST", f"{self.s.llm_base_url}/chat/completions", json=body, headers=self._headers,
                          timeout=timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta

    def warm_up(self) -> None:
        """Load the model into memory ahead of the first request (Ollama only) and keep it loaded for 30 min."""
        url = urlparse(self.s.llm_base_url)
        if not self.s.llm_enabled or not self.check() or url.port != 11434:
            return
        try:
            httpx.post(f"{url.scheme}://{url.netloc}/api/generate",
                       json={"model": self.s.llm_model, "keep_alive": "30m"}, timeout=120)
        except httpx.HTTPError:
            pass
