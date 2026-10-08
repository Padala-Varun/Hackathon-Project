# AI Incident Learning & Prevention Agent (PS01)

Institutional memory for every Live Network Intervention (LNI). The agent learns from the **official dataset provided by the organisers: 23 real JIRA knowledge-base tickets** (CMM, CMG, NRD; releases 24.7–26.7). It can also ingest MOPs, RCAs and logs. Then:

- **Before** a planned LNI, it **warns of known pitfalls** and recommends validation steps. It checks each step of the MOP, gives a risk score, and sends a Teams alert when the risk is high.
- **During** an incident, it **finds technically similar past cases**, however differently they were worded, and shows the root cause and the fix that worked, with confidence scores.
- **After** resolution, it **writes the engineer-verified learning back**, so the next search finds it.

It is **read-only**. Every statement cites the past record it comes from. When nothing matches well enough it answers **"No verified match found"** instead of guessing. Search and ranking run **locally** with Hugging Face embedding and reranker models. The AI writer is **Mistral**: the Mistral API (`ministral-8b-latest`) when a key is set, or Mistral 7B through Ollama fully offline.

Architecture diagram and pipeline details: [docs/architecture.md](docs/architecture.md). Accuracy: [docs/eval_report.md](docs/eval_report.md).

---

## Quick start (Windows, Python 3.10+, Node 20+)

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --port 8000  # first start downloads the HF models (~200 MB) and indexes the data

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173   (one-click demo: http://localhost:5173/#demo)

# 3. Optional: AI writer (pick one)
#    a) Mistral API: put  MISTRAL_API_KEY=<your key>  in a .env file in the project root (never commit it)
#    b) Offline: install Ollama from https://ollama.com, then:
ollama pull mistral               # or: ollama pull qwen2.5:3b  (faster on 8 GB RAM; set LLM_MODEL in backend/.env)
```

The app is fully usable **without** the LLM. Recommendations then come from a deterministic, fully cited draft, and the sidebar shows "AI writer: off". With a Mistral key (or Ollama running), Mistral rewrites the draft in about 3–4 s, and a citation check drops any sentence that does not cite a retrieved record. If the API fails or times out, the cited draft is shown instead.

With the Mistral API, the top matched records (root cause, fix, learning; already privacy-filtered) and the engineer's text are sent to Mistral. Use Ollama when nothing may leave the machine. `mistral-small-latest` has no quota on the free tier, so the default is `ministral-8b-latest` (change with `MISTRAL_MODEL`).

- API docs (OpenAPI): <http://localhost:8000/docs>
- Tests: `cd backend && .venv\Scripts\python -m pytest -q` (27 tests, offline, a few seconds)
- Accuracy report: `python -m scripts.evaluate [--compare-rerankers]` writes [docs/eval_report.md](docs/eval_report.md)

## The dataset

The app loads everything under `data/raw/`:

| Path | What it is |
|---|---|
| `data/raw/official/lni_official.json` | The **official dataset**: 23 JIRA knowledge-base tickets, converted from the organisers' `.msg` e-mails |
| `data/raw/tests/test_incidents.json` | 24 test incidents written in new words (22 with the known right ticket + 2 off-topic), used by `scripts.evaluate` |
| `data/synthetic/` | Practice data from earlier (not loaded by the app; used by the unit tests) |

How the official e-mails were turned into the JSON (`python -m scripts.import_msg --src "../LNI dataset"`):

1. Each `.msg` is parsed (Summary, Components, Product Release, Phase, Description, Technical solution, RCA category…).
2. Forwarded copies of the same ticket are merged (27 e-mails → 25 tickets) and test tickets are dropped (#253, #255).
3. Personal and customer data (reporter, assignee, customer, case ID, project manager), e-mail addresses and SSH keys are removed.
4. Unanswered tickets (#296, #297: "Not yet" / "NA") are kept but marked **Open, no fix yet**.
5. At ingestion the **root cause** and **lesson** are extracted from the free text using clear signals only ("Root Cause:", "The RCA…", "caused by", "Lesson Learned", "always recommend", "make sure", "Don't…"); when nothing clear is found the card shows the problem description instead of guessing.

You can also point the app at a folder of `.msg` files directly (`POST /ingest {"path": "..."}`), or add JSON/CSV/MOP/log files to `data/raw/`; column names are mapped by [backend/field_map.yaml](backend/field_map.yaml). To re-ingest, delete `data/store/` and restart.

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
| `GET /products` | Products (node types) in the history with ticket counts |
| `POST /fingerprint` | Only the fingerprint step (node, product, MOP, release, errors) for a text |
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
| *Agentic:* asks when node / product, release or MOP is missing | `guardrails.clarification_needed` (only asks for what the data can use: with the official tickets it asks for the product, never a MOP) |
| *Agentic:* checks every claim has a citation | `guardrails.verify_citations` drops uncited or unknown-ID statements |
| *RAG:* chunk by field | `app/ingest/chunker.py`; answers cite root cause / resolution / learning / MOP step |
| *API:* mock ticket API, webhook, OpenAPI | `app/api/routes_mock.py`, `notify_webhook` tool |
| Stretch goals | Pre-change risk score, repeat-failure trend dashboard, digest of top recurring issues, field extraction from raw tickets (rule-based) |

## Key design choices (for the pitch)

- **Retrieval-first, LLM-second.** Search, ranking and the cited draft take about 1–2 s and never wait for the LLM. The LLM only rewrites (Mistral API about 3–4 s; local Mistral 7B on an 8 GB laptop about 3–6 tokens/s), and the result is still citation-checked.
- **MiniLM reranker instead of bge-reranker-base.** Same accuracy on our test set at about 10× lower latency (see the eval report).
- **Telecom-aware keyword search.** Identifiers like `CMG-12`, `MOP-UPG-04` and `%BGP-5-ADJCHANGE` stay whole, so exact error codes match exactly.
- **Reworded duplicates are grouped** ("seen 3×"). This makes repeat failures visible and feeds the risk score.
- **Privacy by design.** Customer, case-ID and person columns are dropped at ingestion, e-mails and keys are redacted, search runs locally, and the AI writer can run fully offline (Ollama).
- **Honest extraction.** Root causes and lessons are only extracted from clear wording; a wrong root cause is worse than none.

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
  scripts/import_msg.py       official .msg tickets -> data/raw/official/lni_official.json
  scripts/make_synthetic.py   practice dataset -> data/synthetic (used by the unit tests)
  scripts/evaluate.py         retrieval ablation + end-to-end agent accuracy
  tests/                      unit + API tests (offline)
  field_map.yaml              column aliases + privacy filter
frontend/                 React (Vite + Tailwind) UI
docs/                     architecture, evaluation report
data/raw/                 official dataset (JSON) + test incidents
data/synthetic/           practice data (not loaded by the app)
```

## Ground rules followed

- Only the official dataset (approved for use by the organisers) and synthetic test data. Raw `.msg` e-mails stay out of git; the committed JSON has personal data and secrets removed.
- A human validates before any action. The agent cannot execute anything, and write-back requires a named verifier.
- Every claim traces to a source. Otherwise the answer is "No verified match found".
- Embeddings and reranking run locally (Hugging Face models). The AI writer is Mistral: API by default when a key is set, or local via Ollama for sensitive data, as the brief suggests.
