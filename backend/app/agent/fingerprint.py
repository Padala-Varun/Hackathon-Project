"""Technical fingerprint of a planned LNI or incident: node, node type, vendor, release, MOP/step, error and
command signatures. Uses regexes plus a vocabulary learned from the knowledge base (known nodes, MOPs...)."""
from __future__ import annotations

import re

from ..glossary import CHANGE_TYPE_KEYWORDS, NODE_TYPE_KEYWORDS
from ..ingest.structure import infer_node_type
from ..rag.tokenizer import tokenize
from ..schemas import Fingerprint, LNIRecord, MopDoc
from ..textutil import STEP_RE, find_commands, find_errors, find_mops, find_nodes, find_releases


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def _add(lst: list[str], value: str) -> None:
    if value and value.lower() not in {v.lower() for v in lst}:
        lst.append(value)


class Fingerprinter:
    def __init__(self) -> None:
        self.refresh([], [])

    def refresh(self, records: list[LNIRecord], mops: list[MopDoc]) -> None:
        self.node_info = {r.node.upper(): (r.node_type, r.vendor) for r in records if r.node}
        self.mop_info = {m.mop_id: (m.node_type, m.vendor) for m in mops}
        self.vendors = sorted({r.vendor for r in records if r.vendor} | {m.vendor for m in mops if m.vendor})
        self.node_types = sorted({r.node_type for r in records if r.node_type})

    def nodes_of_type(self, node_type: str) -> list[str]:
        return sorted(n for n, (t, _) in self.node_info.items() if t.lower() == node_type.lower())

    def extract(self, text: str, node: str | None = None, release: str | None = None,
                mop_id: str | None = None) -> Fingerprint:
        low = text.lower()
        fp = Fingerprint()
        for n in find_nodes(text) + ([node.upper()] if node else []):
            _add(fp.nodes, n)
        for m in find_mops(text) + ([mop_id.upper()] if mop_id else []):
            _add(fp.mop_ids, m)
        for r in ([release] if release else []) + find_releases(text):
            _add(fp.releases, r)
        for n in fp.nodes:
            nt, vendor = self.node_info.get(n, (infer_node_type(n), ""))
            _add(fp.node_types, nt)
            _add(fp.vendors, vendor)
        for m in fp.mop_ids:
            nt, vendor = self.mop_info.get(m, ("", ""))
            _add(fp.node_types, nt)
            _add(fp.vendors, vendor)
        for nt, phrases in NODE_TYPE_KEYWORDS.items():
            if any(_has(low, p) for p in phrases):
                _add(fp.node_types, nt)
        for v in self.vendors:
            if _has(low, v.lower()):
                _add(fp.vendors, v)
        fp.mop_steps = sorted({int(s) for s in STEP_RE.findall(text)})
        fp.change_types = [ct for ct, words in CHANGE_TYPE_KEYWORDS.items() if any(w in low for w in words)]
        fp.error_signatures = find_errors(text)[:8]
        fp.commands = find_commands(text)[:6]
        skip = {n.lower() for n in fp.nodes} | {m.lower() for m in fp.mop_ids}
        fp.keywords = list(dict.fromkeys(t for t in tokenize(text) if len(t) > 3 and t not in skip))[:10]
        return fp
