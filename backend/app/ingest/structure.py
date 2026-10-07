"""Turn raw rows / documents into structured records: node, node type, release, MOP step, error, fix."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import yaml

from ..glossary import NODE_PREFIX_TYPES
from ..schemas import LNIRecord, LogSnippet, MopDoc, MopStep
from ..textutil import find_commands, find_errors, find_mops, find_nodes


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def clean(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(clean(v) for v in value if clean(v))
    if isinstance(value, dict):
        return "; ".join(f"{k}: {clean(v)}" for k, v in value.items() if clean(v))
    return str(value).strip()


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(text: str) -> str:
    return EMAIL_RE.sub("[email]", text)


class FieldMapper:
    def __init__(self, path: Path):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.sanitize = {_norm(k) for k in spec.pop("sanitize", [])}
        self.alias: dict[str, dict[str, str]] = {}
        for section, fields in spec.items():
            self.alias[section] = {_norm(a): canon for canon, aliases in fields.items() for a in [canon, *aliases]}

    def aliases_for(self, section: str, canon: str) -> set[str]:
        return {a for a, c in self.alias[section].items() if c == canon}

    def map(self, section: str, raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        mapped: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        table = self.alias[section]
        for key, value in raw.items():
            if _norm(key) in self.sanitize:
                continue  # customer / personal data never enters the knowledge base
            canon = table.get(_norm(key))
            if canon and canon not in mapped:
                mapped[canon] = value
            elif clean(value):
                extra[str(key)] = redact(clean(value))
        return mapped, extra


def infer_node_type(node: str) -> str:
    m = re.match(r"([A-Za-z]+)", node or "")
    return NODE_PREFIX_TYPES.get(m.group(1).upper(), "") if m else ""


def _as_bool(value: Any, default: bool = True) -> bool:
    s = clean(value).lower()
    if not s:
        return default
    return s in {"true", "yes", "y", "1", "verified"}


def to_record(raw: dict[str, Any], mapper: FieldMapper, index: int) -> LNIRecord:
    m, extra = mapper.map("records", raw)
    g = lambda k: redact(clean(m.get(k)))  # noqa: E731
    node = g("node").upper()
    text_blob = " ".join([g("title"), g("description"), g("symptoms")])
    if not node:
        nodes = find_nodes(text_blob)
        node = nodes[0] if nodes else ""
    mop_id = g("mop_id").upper().replace("_", "-")
    if not mop_id:
        mops = find_mops(text_blob)
        mop_id = mops[0] if mops else ""
    step = re.search(r"\d+", g("mop_step"))
    related = [s for s in re.split(r"[,;\s]+", g("related_ids")) if s]
    return LNIRecord(
        id=g("id") or f"LNI-{index:04d}",
        title=g("title") or g("description")[:90],
        date=g("date")[:10],
        change_type=g("change_type"),
        vendor=g("vendor"),
        node=node,
        node_type=g("node_type") or infer_node_type(node),
        release=g("release"),
        mop_id=mop_id,
        mop_step=step.group(0) if step else "",
        description=g("description"),
        symptoms=g("symptoms"),
        error_signature=g("error_signature") or "; ".join(find_errors(text_blob)[:4]),
        commands=g("commands") or "; ".join(find_commands(g("description") + "\n" + g("resolution"))[:4]),
        root_cause=g("root_cause"),
        resolution=g("resolution"),
        learning=g("learning"),
        outcome=g("outcome"),
        severity=g("severity"),
        verified=_as_bool(m.get("verified")),
        related_ids=related,
        extra=extra,
    )


STEP_LINE = re.compile(r"^\s*(?:step\s*)?(\d{1,2})\s*[.):\-]\s+(.+)$", re.I)


def parse_mop(name: str, text: str) -> MopDoc:
    mops = find_mops(text[:500]) or find_mops(name)
    mop_id = mops[0] if mops else Path(name).stem.upper()
    title, node_type, vendor = "", "", ""
    steps: list[MopStep] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            head = s.lstrip("# ").strip()
            if not title and head.lower() not in {"steps", "procedure"}:
                title = re.sub(r"^MOP[-_][A-Z0-9-]+\s*[:\-]\s*", "", head, flags=re.I)
            continue
        kv = re.match(r"^(node\s*type|vendor)\s*:\s*(.+)$", s, re.I)
        if kv:
            if kv.group(1).lower().startswith("node"):
                node_type = kv.group(2).strip()
            else:
                vendor = kv.group(2).strip()
            continue
        sm = STEP_LINE.match(s)
        if sm:
            steps.append(MopStep(no=int(sm.group(1)), text=sm.group(2).strip()))
        elif steps:
            steps[-1].text += " " + s
    return MopDoc(mop_id=mop_id, title=title or mop_id, node_type=node_type, vendor=vendor, steps=steps)


def parse_log(name: str, text: str, index: int) -> LogSnippet:
    node = re.search(r"#\s*node:\s*(\S+)", text, re.I)
    related = re.search(r"#\s*related:\s*(.+)", text, re.I)
    nodes = find_nodes(text)
    return LogSnippet(
        id=f"LOG-{index:02d}",
        node=(node.group(1) if node else (nodes[0] if nodes else "")).upper(),
        related_ids=[s for s in re.split(r"[,;\s]+", related.group(1)) if s] if related else [],
        text=text.strip(),
    )


def parse_tests(rows: list[dict[str, Any]], mapper: FieldMapper) -> list[dict[str, Any]]:
    tests = []
    for i, raw in enumerate(rows, start=1):
        m, _ = mapper.map("tests", raw)
        text = clean(m.get("text"))
        if not text:
            continue
        exp = m.get("expected")
        expected = [clean(e) for e in exp] if isinstance(exp, list) else [s for s in re.split(r"[,;\s]+", clean(exp)) if s]
        mode_raw = clean(m.get("mode")).lower()
        if mode_raw:
            mode = "pre_change" if any(w in mode_raw for w in ("pre", "plan", "change")) else "incident"
        else:
            mode = "pre_change" if re.search(r"\b(planned|using mop|mop-)", text, re.I) else "incident"
        tests.append({"id": clean(m.get("id")) or f"T{i:02d}", "text": text, "expected": expected, "mode": mode})
    return tests
