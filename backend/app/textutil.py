"""Regex helpers shared by ingestion and the fingerprint step."""
from __future__ import annotations

import re

from .glossary import COMMAND_PREFIXES, ERROR_PATTERNS, ERROR_PHRASES

NODE_RE = re.compile(r"(?<![\w-])([A-Za-z]{2,8})-(\d{1,5})\b")  # not inside MOP-UPG-04
NOT_NODE_PREFIXES = {"MOP", "LNI", "INC", "ALM", "ERR", "LRN", "TEST", "CHG", "KB", "SMU", "IKEV", "UTF"}
MOP_RE = re.compile(r"\bMOP[-_][A-Z0-9]+(?:[-_]\d+)?\b", re.I)
RELEASE_RE = re.compile(
    r"(?:\b(?:release|rel|version|ver|firmware|sw|to|r)\s*v?)?(?<![\d.])(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?(?:R\d+)?)(?![\d.])",
    re.I,
)
STEP_RE = re.compile(r"\bstep\s*#?\s*(\d{1,2})\b", re.I)


def join(*parts: str, sep: str = ". ") -> str:
    return sep.join(p.strip().rstrip(".") for p in parts if p and p.strip())


def find_nodes(text: str) -> list[str]:
    out = []
    for m in NODE_RE.finditer(text):
        prefix = m.group(1).upper()
        if prefix in NOT_NODE_PREFIXES or prefix.startswith("MOP"):
            continue
        node = f"{prefix}-{m.group(2)}"
        if node not in out:
            out.append(node)
    return out


def find_mops(text: str) -> list[str]:
    out = []
    for m in MOP_RE.finditer(text):
        mop = m.group(0).upper().replace("_", "-")
        if mop not in out:
            out.append(mop)
    return out


def find_releases(text: str) -> list[str]:
    out = []
    for m in RELEASE_RE.finditer(text):
        rel = m.group(1)
        if rel not in out:
            out.append(rel)
    return out


def find_errors(text: str) -> list[str]:
    out: list[str] = []
    for pat in ERROR_PATTERNS:
        out += [m.group(0) for m in pat.finditer(text)]
    low = text.lower()
    out += [p for p in ERROR_PHRASES if p in low]
    seen, uniq = set(), []
    for e in out:
        if e.lower() not in seen:
            seen.add(e.lower())
            uniq.append(e)
    return uniq


def find_commands(text: str) -> list[str]:
    cmds = re.findall(r"`([^`]{3,120})`", text)
    for line in re.split(r"[\n;]", text):
        s = line.strip().lstrip("$#> ").strip()
        if s.lower().startswith(COMMAND_PREFIXES) and s not in cmds:
            cmds.append(s[:160])
    return cmds
