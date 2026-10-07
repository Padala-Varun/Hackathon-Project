from __future__ import annotations

from ..schemas import Match, Mode

SYSTEM = """You are the LNI Learning Agent. You help telecom change engineers and NOC teams by summarising \
VERIFIED past Live Network Interventions (LNIs).
Rules:
- Use ONLY the evidence records given. Never invent causes, commands, values or record IDs.
- Every bullet must end with the ID(s) of the record(s) it is based on, in square brackets, e.g. [LNI-1012].
- If the evidence does not support an answer, reply exactly: No verified match found.
- You never execute changes. You advise; the engineer decides.
- Reply with 3 to 5 short bullets starting with "- ". No introduction, no closing remarks."""

TASK = {
    "pre_change": "The engineer is PLANNING this change. Warn about known pitfalls and list the validation steps "
                  "to run before and after the change.",
    "incident": "The engineer is handling this INCIDENT. State the most likely root cause, the fix that worked, "
                "and what to validate.",
}


def _clip(text: str, n: int = 260) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def build_messages(mode: Mode, text: str, matches: list[Match], draft: str) -> list[dict[str, str]]:
    evidence = []
    for m in matches[:4]:
        ids = ", ".join(m.all_ids)
        evidence.append(
            f"[{m.record_id}] (confidence {m.confidence}%; also seen as: {ids}; node {m.node}, {m.date}, "
            f"outcome {m.outcome or 'n/a'})\n"
            f"Root cause: {_clip(m.root_cause)}\nFix: {_clip(m.resolution)}\nLearning: {_clip(m.learning, 200)}"
        )
    user = (
        f"{TASK[mode]}\n\nEngineer input:\n{text}\n\nEvidence records:\n" + "\n\n".join(evidence)
        + f"\n\nDraft (rewrite it clearer and shorter, keep every citation):\n{draft}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
