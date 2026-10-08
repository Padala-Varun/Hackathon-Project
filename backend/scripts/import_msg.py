"""Convert the official JIRA ticket emails (.msg) into a clean JSON dataset for the app.

  python -m scripts.import_msg --src "../LNI dataset" --out ../data/raw/official/lni_official.json

What it does: reads every .msg, merges forwards/updates of the same ticket, drops test tickets, removes personal
fields (reporter, assignee, customer, case id, project manager) and secrets (private/public keys, e-mails), and
writes one row per ticket. The app can also ingest the .msg folder directly; this JSON is what gets committed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import PROJECT_DIR
from app.ingest.msg_reader import is_junk, merge_tickets, read_msg, to_row
from app.ingest.structure import redact


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=PROJECT_DIR / "LNI dataset")
    ap.add_argument("--out", type=Path, default=PROJECT_DIR / "data" / "raw" / "official" / "lni_official.json")
    a = ap.parse_args()

    files = sorted(a.src.rglob("*.msg"))
    tickets = merge_tickets([r for p in files if (r := read_msg(p))])
    junk = [t["ticket_key"] for t in tickets if is_junk(t)]
    rows = [{k: redact(v) if isinstance(v, str) else v for k, v in to_row(t).items()} for t in tickets if not is_junk(t)]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    open_ = [r["ticket_key"] for r in rows if not r["technical_solution"]]
    print(f"{len(files)} emails -> {len(tickets)} tickets -> {len(rows)} rows written to {a.out}")
    print(f"dropped test tickets: {junk or 'none'} | open (no fix yet): {open_ or 'none'}")


if __name__ == "__main__":
    main()
