"""Read raw files from a dataset folder. Classifies files into LNI records, test incidents, MOPs and logs.

Folder hints are used when present (lni/, tests/, mops/, logs/) but are not required: tabular files with an
"expected" column are treated as test sets, documents that look like a MOP become MOPs, *.log files are logs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

TABULAR = {".json", ".jsonl", ".csv", ".xlsx"}
DOCS = {".md", ".txt", ".docx", ".pdf"}


@dataclass
class RawDataset:
    records: list[dict[str, Any]] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    mops: list[tuple[str, str]] = field(default_factory=list)  # (file name, text)
    logs: list[tuple[str, str]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def read_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records")
    if suffix == ".xlsx":
        return pd.read_excel(path, dtype=str).fillna("").to_dict("records")
    if suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
        return [data]
    return []


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        import docx

        doc = docx.Document(str(path))
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(lines)
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_test_rows(rows: list[dict[str, Any]], expected_aliases: set[str]) -> bool:
    return bool(rows) and any(_norm(k) in expected_aliases for k in rows[0].keys())


def _looks_like_mop(name: str, text: str) -> bool:
    head = text[:2000].lower()
    return bool(re.search(r"\bmop[-_ ]?[a-z0-9]", name, re.I)) or "method of procedure" in head or bool(
        re.search(r"\bmop-[a-z0-9]+-\d+", head)
    )


def scan(root: Path, expected_aliases: set[str]) -> RawDataset:
    ds = RawDataset()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        suffix = path.suffix.lower()
        parts = {p.lower() for p in path.relative_to(root).parts[:-1]}
        try:
            if suffix in TABULAR:
                rows = read_rows(path)
                if "tests" in parts or "test" in parts or _is_test_rows(rows, expected_aliases):
                    ds.tests += rows
                else:
                    ds.records += rows
            elif suffix == ".log" or any("log" in p for p in parts):
                ds.logs.append((path.name, read_text(path)))
            elif suffix in DOCS:
                text = read_text(path)
                if any("mop" in p for p in parts) or _looks_like_mop(path.name, text):
                    ds.mops.append((path.name, text))
                else:
                    continue
            else:
                continue
            ds.files.append(str(path.relative_to(root)))
        except Exception as exc:  # one bad file must not stop ingestion
            print(f"[ingest] skipped {path.name}: {exc}")
    return ds
