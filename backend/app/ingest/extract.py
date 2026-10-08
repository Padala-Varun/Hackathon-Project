"""Rule-based field extraction from free-text tickets: find the root cause and the lesson / pre-check when a
ticket has no dedicated field for them (e.g. JIRA knowledge-base tickets with only Description + Solution).

Precision over recall: only clear signals are used. When nothing clear is found the field stays empty and the
UI shows the problem description instead - a wrong root cause is worse than none."""
from __future__ import annotations

import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])|\n+")
_HEADER = re.compile(r"^\s*(?:\d+\.\s*)?(root cause|rca|lessons? learned(?:\s*/\s*preventive action)?|preventive action)\s*:?\s*(.*)$", re.I)
_NEXT_SECTION = re.compile(
    r"^\s*(?:\d+\.\s*)?(resolution|issue|error|lessons? learned|preventive action|root cause|step\s*\d+|_{5,}|solution|workaround)\b"
    r"|^\s*\d+\.\s+[A-Z]", re.I)
_NOISE = re.compile(r"^\s*(#|\$|\[|step\s*\d|[-*]\s*(su|ssh)\b|[a-z_]+:\s*$)|={4,}|_{4,}", re.I)
_LEAD = re.compile(r"^\s*(\d+[).]\s*)+")

ROOT_CAUSE = re.compile(r"\b(root cause|the rca|caused by|is not supported|was disabled|were disabled|was missing|"
                        r"were missing|was not configured|were not configured|used the same|was configured to)\b", re.I)
ROOT_CAUSE_DESC_ONLY = re.compile(r"\bdue to this\b", re.I)
LEARN_STRONG = re.compile(r"\b(recommend\w*|make sure|make ensure|important:|lessons? learned|always)\b|^(do not|don't|never|avoid|ensure)\b", re.I)
LEARN_WEAK = re.compile(r"\b(should be|instead of|need to|needs to|validate)\b", re.I)


def _sentences(text: str) -> list[str]:
    out = []
    for s in _SENT_SPLIT.split(text or ""):
        s = _LEAD.sub("", s.strip(" \t-•*"))
        if 25 <= len(s) <= 400 and not _NOISE.search(s) and sum(c.isalpha() for c in s) > len(s) * 0.55:
            out.append(s)
    return out


def _sections(text: str, kinds: tuple[str, ...]) -> list[str]:
    """Collect the lines that follow headers like 'Root Cause:' or 'Lesson Learned / Preventive Action:'."""
    found, lines = [], (text or "").splitlines()
    for i, line in enumerate(lines):
        m = _HEADER.match(line)
        if not m or not m.group(1).lower().startswith(kinds):
            continue
        body = [m.group(2).strip()] if m.group(2).strip() else []
        for nxt in lines[i + 1:]:
            if _NEXT_SECTION.match(nxt) or (body and not nxt.strip()):
                break
            if nxt.strip():
                body.append(nxt.strip())
        if body:
            found.append(" ".join(_sentences(" ".join(body))[:2]) or " ".join(body))
    return [f for f in found if f]


def _join(parts: list[str], limit: int) -> str:
    out: list[str] = []
    for p in dict.fromkeys(parts):
        if out and len(" ".join(out + [p])) > limit:
            break
        out.append(p.rstrip(".:") + ".")
    text = " ".join(out)
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def extract_root_cause(description: str, solution: str, limit: int = 420) -> str:
    sections = _sections(solution, ("root cause", "rca")) + _sections(description, ("root cause", "rca"))
    if sections:
        return _join(sections, limit)
    hits = [s for s in _sentences(solution) + _sentences(description) if ROOT_CAUSE.search(s)]
    hits += [s for s in _sentences(description) if ROOT_CAUSE_DESC_ONLY.search(s)]
    return _join(hits[:2], limit) if hits else ""


def extract_learning(description: str, solution: str, limit: int = 420) -> str:
    sections = _sections(solution, ("lesson", "preventive")) + _sections(description, ("lesson", "preventive"))
    if sections:
        return _join(sections, limit)
    sol = _sentences(solution)
    strong = [s for s in sol if LEARN_STRONG.search(s)] + [s for s in _sentences(description) if LEARN_STRONG.search(s)
                                                          and re.search(r"make (sure|ensure)|recommend", s, re.I)]
    weak = [s for s in sol if LEARN_WEAK.search(s) and s not in strong]
    hits = strong[:2] or weak[:2]
    return _join(hits, limit) if hits else ""
