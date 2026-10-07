"""Measure retrieval accuracy on the test incidents and write docs/eval_report.md.

  python -m scripts.evaluate                 # retrieval ablation + full agent
  python -m scripts.evaluate --compare-rerankers   # also try BAAI/bge-reranker-base (slow on CPU)

A test is a HIT@k when any expected record (the known correct past match, incl. its reworded duplicates)
is among the top-k results. Tests with no expected record are out-of-scope: the agent must answer
"no verified match".
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from app.config import PROJECT_DIR, settings
from app.rag.models import CrossEncoderReranker
from app.rag.search import SearchConfig
from app.schemas import RecommendRequest
from app.services import init_services

CONFIGS = {
    "BM25 keyword only": SearchConfig(dense=False, bm25=True, rerank=False, fingerprint=False),
    "Dense semantic only": SearchConfig(dense=True, bm25=False, rerank=False, fingerprint=False),
    "Hybrid (RRF)": SearchConfig(dense=True, bm25=True, rerank=False, fingerprint=False),
    "Hybrid + rerank": SearchConfig(dense=True, bm25=True, rerank=True, fingerprint=False),
    "Hybrid + rerank + fingerprint": SearchConfig(),
}


def score(ranked_ids: list[list[str]], expected: set[str]) -> tuple[int, int, float]:
    for i, ids in enumerate(ranked_ids):
        if expected & set(ids):
            return int(i == 0), int(i < 3), 1.0 / (i + 1)
    return 0, 0, 0.0


def eval_retrieval(kb, tests, cfg: SearchConfig) -> dict:
    h1 = h3 = 0
    mrr, times = 0.0, []
    for t in tests:
        fp = kb.fingerprinter.extract(t["text"])
        t0 = time.time()
        ms = kb.searcher.match_records(t["text"], fp=fp, top_k=10, cfg=cfg, group=False)
        times.append(time.time() - t0)
        a, b, c = score([[m.record_id] for m in ms], set(t["expected"]))
        h1, h3, mrr = h1 + a, h3 + b, mrr + c
    n = len(tests)
    return {"hit@1": h1 / n, "hit@3": h3 / n, "mrr": mrr / n, "latency": sum(times) / n}


def eval_agent(agent, tests) -> tuple[dict, list[str]]:
    rows, in_scope, out_scope = [], [t for t in tests if t["expected"]], [t for t in tests if not t["expected"]]
    h1 = h3 = 0
    cites_ok = cites_total = 0
    refusals = 0
    times = []
    for t in tests:
        t0 = time.time()
        rec = agent.run_sync(RecommendRequest(text=t["text"], mode=t["mode"], skip_clarification=True,
                                              use_llm=False, notify=False))
        times.append(time.time() - t0)
        retrieved = {i for m in rec.matches for i in m.all_ids} | {c for s in rec.mop_steps for w in s.warnings for c in w.citations}
        for item in rec.items + rec.prechecks:
            cites_total += 1
            cites_ok += bool(item.citations) and set(item.citations) <= retrieved
        if t["expected"]:
            a, b, _ = score([m.all_ids for m in rec.matches] if rec.status == "ok" else [], set(t["expected"]))
            h1, h3 = h1 + a, h3 + b
            verdict = "HIT@1" if a else ("HIT@3" if b else "MISS")
        else:
            refusals += rec.status == "no_match"
            verdict = "correctly refused" if rec.status == "no_match" else "FALSE MATCH"
        top = f"{rec.matches[0].record_id} ({rec.matches[0].confidence}%)" if rec.matches else "-"
        rows.append(f"| {t['id']} | {t['mode']} | {t['text'][:70]} | {top} | {verdict} |")
    summary = {
        "hit@1": h1 / max(1, len(in_scope)), "hit@3": h3 / max(1, len(in_scope)),
        "refusal": refusals / max(1, len(out_scope)) if out_scope else None,
        "citations": cites_ok / max(1, cites_total), "latency": sum(times) / max(1, len(times)),
        "n_in": len(in_scope), "n_out": len(out_scope),
    }
    return summary, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare-rerankers", action="store_true")
    ap.add_argument("--out", type=Path, default=PROJECT_DIR / "docs" / "eval_report.md")
    args = ap.parse_args()

    kb, agent = init_services(settings)
    tests = kb.tests
    in_scope = [t for t in tests if t["expected"]]
    if not tests:
        raise SystemExit("No test incidents found under data/raw (tests/*.json|csv with an 'expected' column).")
    print(f"{len(in_scope)} in-scope test incidents, {len(tests) - len(in_scope)} out-of-scope; "
          f"{kb.stats()['records']} records indexed")

    results = {}
    for name, cfg in CONFIGS.items():
        results[name] = eval_retrieval(kb, in_scope, cfg)
        r = results[name]
        print(f"{name:32s} hit@1 {r['hit@1']:.0%}  hit@3 {r['hit@3']:.0%}  MRR {r['mrr']:.2f}  {r['latency']:.2f}s")
    if args.compare_rerankers and kb.reranker:
        original = kb.searcher.reranker
        for model in ("BAAI/bge-reranker-base",):
            if model == original.name:
                continue
            kb.searcher.reranker = CrossEncoderReranker(model, settings.models_dir)
            name = f"Full pipeline with {model.split('/')[-1]}"
            results[name] = eval_retrieval(kb, in_scope, SearchConfig())
            r = results[name]
            print(f"{name:32s} hit@1 {r['hit@1']:.0%}  hit@3 {r['hit@3']:.0%}  MRR {r['mrr']:.2f}  {r['latency']:.2f}s")
        kb.searcher.reranker = original

    agent_summary, rows = eval_agent(agent, tests)
    a = agent_summary
    print(f"Agent: hit@1 {a['hit@1']:.0%} hit@3 {a['hit@3']:.0%} | out-of-scope refused "
          f"{(a['refusal'] or 0):.0%} | citations valid {a['citations']:.0%} | {a['latency']:.2f}s per run")

    lines = [
        "# Evaluation report", "",
        f"Dataset: {kb.stats()['records']} LNI records, {kb.stats()['mops']} MOPs, {kb.stats()['logs']} logs. "
        f"Test set: {a['n_in']} incidents with a known correct past match + {a['n_out']} out-of-scope.", "",
        f"Models: embeddings `{kb.embedder.name}`, reranker `{kb.reranker.name if kb.reranker else 'none'}`, "
        f"vector store `{kb.index.store.name}`, confidence threshold {settings.match_threshold}%.", "",
        "## Retrieval ablation", "", "| Pipeline | Hit@1 | Hit@3 | MRR | Latency |", "|---|---|---|---|---|",
    ]
    lines += [f"| {n} | {r['hit@1']:.0%} | {r['hit@3']:.0%} | {r['mrr']:.2f} | {r['latency']:.2f}s |" for n, r in results.items()]
    lines += [
        "", "## Agent (end to end, LLM off)", "",
        f"- Correct past match ranked first: **{a['hit@1']:.0%}**, in top 3: **{a['hit@3']:.0%}**",
        f"- Out-of-scope incidents answered with \"No verified match found\": **{(a['refusal'] or 0):.0%}**",
        f"- Recommendation statements citing a retrieved record: **{a['citations']:.0%}**",
        f"- Average time per agent run: {a['latency']:.2f}s", "",
        "| Test | Mode | Incident / planned LNI | Top match | Result |", "|---|---|---|---|---|", *rows, "",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
