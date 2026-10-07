# AI Incident Learning & Prevention Agent (PS01)

Institutional memory for every Live Network Intervention (LNI). The agent ingests past LNI tickets, MOPs, RCAs and logs, and then:

- **Before** a planned LNI, it **warns of known pitfalls** and recommends validation steps. It checks each step of the MOP, gives a risk score, and sends a Teams alert when the risk is high.
- **During** an incident, it **finds technically similar past cases**, however differently they were worded, and shows the root cause and the fix that worked, with confidence scores.
- **After** resolution, it **writes the engineer-verified learning back**, so the next search finds it.

It is **read-only**. Every statement cites the past record it comes from. When nothing matches well enough it answers **"No verified match found"** instead of guessing. Everything runs **offline on a laptop**: Mistral 7B through Ollama, plus Hugging Face embedding and reranker models. No data leaves the machine.

Architecture diagram and pipeline details: [docs/architecture.md](docs/architecture.md). Accuracy: [docs/eval_report.md](docs/eval_report.md).

---

## Quick start (Windows, Python 3.10+, Node 20+)

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.make_synthetic  # stand-in dataset -> data/raw (skip if you copied the official one)
uvicorn app.main:app --port 8000  # first start downloads the HF models (~200 MB) and indexes the data

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173   (one-click demo: http://localhost:5173/#demo)

# 3. Optional: local LLM (no API key)
#    install Ollama from https://ollama.com, then:
ollama pull mistral               # or: ollama pull qwen2.5:3b  (faster on 8 GB RAM; set LLM_MODEL in backend/.env)
```

The app is fully usable **without** the LLM. Recommendations then come from a deterministic, fully cited draft, and the header shows "LLM offline". When Ollama is running, Mistral rewrites the draft, and a citation check drops any uncited sentence.

- API docs (OpenAPI): <http://localhost:8000/docs>
- Tests: `cd backend && .venv\Scripts\python -m pytest -q` (20 tests, offline, ~2 s)
- Accuracy report: `python -m scripts.evaluate [--compare-rerankers]` writes [docs/eval_report.md](docs/eval_report.md)

## Using the official dataset

1. Put the files under `data/raw/`. Subfolders help but are optional:
   - `lni/*.json|csv` for the LNI records
   - `mops/*.md|docx|pdf` for the MOPs
   - `logs/*.log|txt` for the log snippets
   - `tests/*.json|csv` for the test incidents (any file with an `expected` column)
2. Column names are mapped by [backend/field_map.yaml](backend/field_map.yaml). Add an alias there if a column isn't recognised. No code change is needed, and unknown columns are still indexed.
3. Re-ingest with `POST /ingest` (or the `/docs` page), or delete `data/store/` and restart.
4. Run `python -m scripts.evaluate` to measure accuracy on the official 20 test incidents.

## API

| Endpoint | Purpose |
|---|---|
| `POST /ingest` | Ingest a folder or raw records, then rebuild the index |
| `POST /match` | Fingerprint + hybrid search + rerank → ranked past LNIs with confidence and evidence (no LLM) |
| `POST /recommend` | Run the full agent (`mode`: `pre_change` / `incident`). `/recommend/stream` streams the same run as SSE |
| `POST /feedback` | Write back a verified learning, or confirm that a past fix worked (requires `verified_by`) |
| `GET /tickets`, `GET /tickets/{id}`, `POST /tickets/{id}/learnings` | Mock ticketing API |
| `GET /nodes/{node}/history` | Node history lookup |
| `POST /mock/webhook`, `GET /notifications` | Mock Teams webhook receiver |
| `GET /trends`, `GET /digest` | Repeat-failure trends and a digest of top recurring issues |
| `GET /tools` | The agent's tool registry (JSON schemas) |

## How it meets the brief

| Requirement | Where |
|---|---|
| Ingest and index the dataset | `app/ingest/*`, `app/rag/index.py`, `POST /ingest` |
| Hybrid search with reranking | Dense (ChromaDB) + BM25 + metadata filters → RRF → cross-encoder (`app/rag/search.py`) |
| Recommendation with citations and confidence | `app/agent/runner.py`; every item carries record IDs and a 0-100 confidence |
| REST API and simple UI | FastAPI (auto OpenAPI) + React UI |
| Write-back of a verified learning | `POST /feedback` → verified record, indexed immediately, ticket updated |
| *Agentic:* plans its own searches, re-queries on low confidence | `app/agent/planner.py`; plans by symptom, node history, MOP step and error signature; up to 2 re-query rounds (drop filters + glossary expansion, then field-targeted search) |
| *Agentic:* asks when node, release or MOP is missing | `guardrails.clarification_needed` |
| *Agentic:* checks every claim has a citation | `guardrails.verify_citations` drops uncited or unknown-ID statements |
| *RAG:* chunk by field | `app/ingest/chunker.py`; answers cite root cause / resolution / learning / MOP step |
| *API:* mock ticket API, webhook, OpenAPI | `app/api/routes_mock.py`, `notify_webhook` tool |
| Stretch goals | Pre-change risk score, repeat-failure trend dashboard, digest of top recurring issues |

## Key design choices (for the pitch)

- **Retrieval-first, LLM-second.** On an 8 GB CPU laptop, Mistral 7B writes at about 3–6 tokens/s. Search, ranking and the cited draft take about 1–2 s and never wait for the LLM. The LLM only rewrites, and the result is still citation-checked.
- **MiniLM reranker instead of bge-reranker-base.** Same accuracy on our test set at about 10× lower latency (see the eval report).
- **Telecom-aware keyword search.** Identifiers like `CMG-12`, `MOP-UPG-04` and `%BGP-5-ADJCHANGE` stay whole, so exact error codes match exactly.
- **Reworded duplicates are grouped** ("seen 3×"). This makes repeat failures visible and feeds the risk score.
- **Privacy by design.** Customer, case-ID and person columns are dropped at ingestion, e-mails are redacted, and inference is local.

## Project layout

```
backend/
  app/
    main.py               FastAPI app
    config.py             all settings (override in backend/.env)
    ingest/               loaders, field mapping + privacy filter, chunk-by-field
    rag/                  tokenizer, models (HF embeddings/reranker), vector store, index, hybrid search
    agent/                fingerprint, planner, tools, guardrails, LLM client, runner, write-back
    api/                  core routes + mock integrations
  scripts/make_synthetic.py   synthetic dataset (100 LNIs, 6 MOPs, logs, 22 test incidents)
  scripts/evaluate.py         retrieval ablation + end-to-end agent accuracy
  tests/                      unit + API tests (offline)
  field_map.yaml              column aliases + privacy filter
frontend/                 React (Vite + Tailwind) UI
docs/                     architecture, evaluation report
data/raw/                 dataset (synthetic stand-in)
```

## Ground rules followed

- Synthetic data only. Real tickets are excluded via `.gitignore` and never ingested.
- A human validates before any action. The agent cannot execute anything, and write-back requires a named verifier.
- Every claim traces to a source. Otherwise the answer is "No verified match found".
- AI runs locally (Mistral via Ollama, Hugging Face models), as the brief suggests for sensitive data.
