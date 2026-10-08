"""The agent decides which searches to run from the fingerprint, and how to re-query when confidence is low."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..glossary import SYNONYMS
from ..schemas import Fingerprint, Mode


@dataclass
class PlanStep:
    tool: str
    args: dict[str, Any]
    reason: str
    merge: bool = field(default=True)  # merge results into the candidate matches

    def describe(self) -> dict[str, Any]:
        return {"tool": self.tool, "args": self.args, "reason": self.reason}

    def label(self) -> str:
        shown = ", ".join(f"{k}={str(v)[:60]!r}" for k, v in self.args.items() if v)
        return f"{self.tool}({shown})"


def expand_query(text: str) -> str:
    low = text.lower()
    extra = [w for key, words in SYNONYMS.items() if key in low for w in words if w not in low]
    return text + (" " + " ".join(dict.fromkeys(extra)) if extra else "")


def _filter_node_type(fp: Fingerprint) -> str | None:
    """Hard-filter only when the node type comes from an explicit node or MOP (listed first in the fingerprint).
    A keyword such as "NetAct" may just name where the symptom was seen, so it only earns a ranking bonus."""
    return fp.node_types[0] if (fp.nodes or fp.mop_ids) and fp.node_types else None


def make_plan(mode: Mode, fp: Fingerprint, text: str, mop_title: str = "",
              explicit_type: str | None = None) -> list[PlanStep]:
    node = fp.nodes[0] if fp.nodes else None
    node_type = explicit_type or _filter_node_type(fp)
    steps: list[PlanStep] = []
    if mode == "pre_change":
        if node:
            steps.append(PlanStep("node_history", {"node": node}, f"Check what happened in past LNIs on {node}", merge=False))
        if fp.mop_ids:
            steps.append(PlanStep("search_by_mop_step", {"mop_id": fp.mop_ids[0]},
                                  f"Look for known pitfalls at each step of {fp.mop_ids[0]}"))
        query = f"{text}. {mop_title}".strip(". ")
        if fp.node_types and fp.releases:
            steps.append(PlanStep("search_by_fingerprint", {"node_type": fp.node_types[0], "release": fp.releases[0]},
                                  f"Known issues recorded for {fp.node_types[0]} release {fp.releases[0]} (fingerprint match)"))
        steps.append(PlanStep("search_by_symptom", {"text": query, "node_type": node_type},
                              "Find past LNIs similar to this planned change"
                              + (f" (metadata filter: node type {node_type})" if node_type else "")))
    else:
        steps.append(PlanStep("search_by_symptom", {"text": text, "node_type": node_type},
                              "Find technically similar past incidents"
                              + (f" (metadata filter: node type {node_type})" if node_type else "")))
        if fp.error_signatures:
            steps.append(PlanStep("search_by_symptom",
                                  {"text": "; ".join(fp.error_signatures), "fields": ["symptom", "log"]},
                                  "Match the exact error signature against symptoms and logs"))
        if node:
            steps.append(PlanStep("node_history", {"node": node}, f"Recent changes on {node} may explain the incident",
                                  merge=False))
    return steps


def requery_steps(round_no: int, fp: Fingerprint, text: str) -> tuple[str, list[PlanStep]]:
    expanded = expand_query(text)
    if round_no == 1:
        return ("dropping metadata filters and expanding the query with the domain glossary",
                [PlanStep("search_by_symptom", {"text": expanded}, "Re-query without filters, with synonyms")])
    return ("searching root-cause / learning / resolution fields only, with keywords",
            [PlanStep("search_by_symptom", {"text": expanded + " " + " ".join(fp.keywords),
                                            "fields": ["root_cause", "learning", "resolution"]},
                      "Re-query targeted at root cause and learnings")])
