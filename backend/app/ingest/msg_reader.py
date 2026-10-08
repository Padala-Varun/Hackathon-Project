"""Read Outlook .msg JIRA notification emails ("[JIRADC2] Updates for PACOSDKB-213: ...") into raw ticket rows.

The plain-text body holds "Label:<TAB>value" lines; multi-line values (Description, Technical solution provided)
continue until the next label. Several emails can describe the same ticket (forwards, updates): they are merged
by ticket key, keeping the longest value of each field.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
LABEL_RE = re.compile(r"^\s*([A-Z][A-Za-z .\-/()]{1,40}?)\s*:\t(.*)$")
URL_RE = re.compile(r"\s*<(?:https?|mailto):[^>]+>")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)
PUBLIC_KEY_RE = re.compile(r"\b(ssh-(?:rsa|ed25519)|ecdsa-sha2-nistp\d+) [A-Za-z0-9+/=]{40,}")
SUBJECT_PREFIX_RE = re.compile(r"^\s*(?:(?:FW|Fw|RE|Re)\s*:\s*)*\[[^\]]+\]\s*Updates for [A-Z]+-\d+\s*:\s*")
PLACEHOLDER_FIX = {"", "na", "n/a", "not yet", "not yet.", "test", "tbd", "-"}
END_MARKERS = ("This message was sent by Atlassian Jira", "If image attachments aren't displayed")

# JIRA field label -> our raw column name (the field map then maps these to the canonical record)
LABELS = {
    "Summary": "title", "Issue Type": "issue_type", "Components": "components", "Created": "created",
    "Labels": "labels", "Priority": "priority", "Build": "build", "Market": "market", "Phase": "phase",
    "Product Release": "product_release", "Program.": "program", "RCA Category": "rca_category",
    "Sub-Components": "sub_components", "Technical solution provided": "technical_solution",
    "Technology": "technology", "Type": "platform", "Description": "description",
    # personal / customer data: read so it can be dropped explicitly by the privacy filter
    "Assignee": "assignee", "Reporter": "reporter", "Case ID": "case_id", "Customers": "customers",
    "Project Manager": "project_manager",
}


def _clean(text: str) -> str:
    text = URL_RE.sub("", text)
    text = PRIVATE_KEY_RE.sub("[private key removed]", text)
    text = PUBLIC_KEY_RE.sub(r"\1 [public key removed]", text)
    lines = [ln.rstrip(" \t ") for ln in text.replace("\r\n", "\n").split("\n")]
    out = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", out)


def parse_body(body: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    current = None
    for line in body.replace("\r\n", "\n").split("\n"):
        if any(m in line for m in END_MARKERS):
            break
        m = LABEL_RE.match(line)
        if m and m.group(1).strip() in LABELS:
            current = LABELS[m.group(1).strip()]
            fields.setdefault(current, []).append(m.group(2))
        elif current:
            fields[current].append(line)
    return {k: _clean("\n".join(v)) for k, v in fields.items()}


def _iso_date(value: str) -> str:
    for fmt in ("%d.%m.%Y %I:%M %p", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip()[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return value[:10]


def read_msg(path: Path) -> dict[str, Any] | None:
    import extract_msg  # optional dependency, only needed for .msg datasets

    msg = extract_msg.Message(str(path))
    try:
        subject = msg.subject or ""
        body = msg.body or ""
        sent = msg.date
    finally:
        msg.close()
    key = KEY_RE.search(subject)
    if not key:
        return None
    row = parse_body(body)
    row["ticket_key"] = key.group(1)
    row["title"] = SUBJECT_PREFIX_RE.sub("", row.get("title") or subject).strip()
    row["created"] = _iso_date(row.get("created", "")) or (sent.date().isoformat() if sent else "")
    status = re.search(rf"{key.group(1)}\s*(?:<[^>]+>)?\s*\t?\s*(Open|Closed|Resolved|Done|In Progress)\b", body)
    row["jira_status"] = status.group(1) if status else ""
    row["vendor"] = "Nokia" if "nokia" in body.lower() else ""
    row["source_file"] = path.name
    return row


def merge_tickets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Several emails per ticket (forwards / updates): keep the longest value of every field."""
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        cur = merged.setdefault(row["ticket_key"], {})
        for k, v in row.items():
            if k == "title" and cur.get("title"):
                continue  # keep the first clean title, not a longer forwarded subject
            if len(str(v or "")) > len(str(cur.get(k) or "")):
                cur[k] = v
    return [merged[k] for k in sorted(merged, key=lambda s: int(s.split("-")[1]))]


def is_junk(t: dict[str, Any]) -> bool:
    """Test tickets ("Testing email template - please ignore", solution "Test") carry no knowledge."""
    title = (t.get("title") or "").lower()
    fix = (t.get("technical_solution") or "").strip().lower()
    return ("please ignore" in title or title.startswith("test ") or fix == "test") and len(t.get("description") or "") < 40


def to_row(t: dict[str, Any]) -> dict[str, Any]:
    """Structure one JIRA KB ticket into the dataset's column names (mapped by field_map.yaml)."""
    components = [c.strip() for c in (t.get("components") or "").split(",") if c.strip()]
    family = re.match(r"[A-Za-z]+", components[0]).group(0).upper() if components else ""
    fix = t.get("technical_solution") or ""
    has_fix = fix.strip().lower().rstrip(".") not in {p.rstrip(".") for p in PLACEHOLDER_FIX}
    return {
        "ticket_key": t["ticket_key"],
        "title": t.get("title", ""),
        "created": t.get("created", ""),
        "phase": t.get("phase", ""),
        "vendor": t.get("vendor", ""),
        "node_type": family,
        "product_release": t.get("product_release", ""),
        "problem_description": t.get("description", ""),
        "technical_solution": fix if has_fix else "",
        "outcome": "Resolved" if has_fix else "Open - no fix yet",
        "Components": ", ".join(components),
        "Build": t.get("build", ""),
        "RCA category": t.get("rca_category", ""),
        "Sub-components": t.get("sub_components", ""),
        "Labels": t.get("labels", ""),
        "Technology": t.get("technology", ""),
        "Platform": t.get("platform", ""),
        "Market": t.get("market", ""),
    }


def read_folder(folder: Path) -> list[dict[str, Any]]:
    """All .msg files in a folder -> merged, cleaned, structured rows (junk tickets dropped)."""
    tickets = merge_tickets([r for p in sorted(folder.rglob("*.msg")) if (r := read_msg(p))])
    return [to_row(t) for t in tickets if not is_junk(t)]
