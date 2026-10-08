"""Guardrails: ask for missing context, enforce citations, refuse to guess."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..glossary import RELEASE_CHANGES
from ..schemas import Clarification, Fingerprint, Mode, RecommendRequest

if TYPE_CHECKING:
    from ..services import KnowledgeBase

NO_MATCH = "No verified match found"


def clarification_needed(mode: Mode, fp: Fingerprint, req: RecommendRequest, kb: "KnowledgeBase") -> Clarification | None:
    if req.skip_clarification:
        return None
    types = {t.lower() for t in fp.node_types}
    has_nodes = bool(kb.fingerprinter.node_info)  # only ask for what the history can actually use
    products = kb.fingerprinter.node_types
    if mode == "pre_change":
        if has_nodes and not fp.nodes:
            opts = [n for t in fp.node_types for n in kb.fingerprinter.nodes_of_type(t)] or sorted(kb.fingerprinter.node_info)
            return Clarification(field="node", question="Which node is this LNI planned on? I use it to check the node's history.",
                                 options=opts[:12])
        if not has_nodes and not fp.node_types and products:
            return Clarification(field="node_type", question="Which product is this change on? I use it to search the right history.",
                                 options=products)
        if kb.mops and not fp.mop_ids:
            opts = [m.mop_id for m in kb.mops.values() if not types or m.node_type.lower() in types] or list(kb.mops)
            return Clarification(field="mop_id", question="Which MOP will be followed? I check known pitfalls step by step.",
                                 options=opts)
        if set(fp.change_types) & RELEASE_CHANGES and not fp.releases:
            opts = sorted({r.release for r in kb.records.values() if r.release and (not types or r.node_type.lower() in types)})
            target = fp.nodes[0] if fp.nodes else (fp.node_types[0] if fp.node_types else "it")
            return Clarification(field="release", question=f"Which target release is {target} being upgraded to?",
                                 options=opts)
    elif not fp.nodes and not fp.node_types:
        if has_nodes:
            return Clarification(field="node", question="Which node (or node type) is affected? It lets me filter by platform "
                                                        "and check the node's recent changes.",
                                 options=sorted(kb.fingerprinter.node_info)[:12])
        if products:
            return Clarification(field="node_type", question="Which product is affected? It lets me search the right history.",
                                 options=products)
    return None


def id_pattern(record_ids: list[str]) -> re.Pattern[str]:
    prefixes = sorted({m.group(0) for i in record_ids if (m := re.match(r"[A-Za-z]+", i))} | {"LNI", "LRN"})
    return re.compile(r"\b(?:" + "|".join(map(re.escape, prefixes)) + r")-[A-Za-z0-9]+\b")


_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _statements(text: str) -> list[str]:
    """LLM text -> one plain-text statement per bullet: wrapped lines and code blocks are joined back into
    their bullet, markdown (**bold**, `code`, ``` fences) is removed."""
    out: list[str] = []
    for line in text.replace("\r", "").split("\n"):
        s = line.strip()
        if not s or s.startswith("```") or set(s) <= set("-*_= "):
            continue
        if _BULLET.match(s) or not out:
            out.append(_BULLET.sub("- ", s, count=1))
        else:
            out[-1] += " " + s
    return [re.sub(r"\*\*|__|`", "", s).strip() for s in out]


def verify_citations(text: str, allowed: set[str], pattern: re.Pattern[str]) -> tuple[list[str], list[str]]:
    """Keep only statements that cite at least one retrieved record and no unknown record."""
    kept, dropped = [], []
    for s in _statements(text):
        if not s or s.endswith(":") and len(s) < 60:
            continue
        if s.lstrip("-* ").lower().startswith(NO_MATCH.lower()):
            kept.append(s)
            continue
        ids = set(pattern.findall(s))
        mops = {m for m in allowed if m.startswith("MOP") and m in s}
        valid, invalid = (ids & allowed) | mops, ids - allowed
        (kept if valid and not invalid else dropped).append(s)
    return kept, dropped
