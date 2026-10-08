# Architecture

## At a glance

```mermaid
flowchart LR
    subgraph Inputs
        A[LNI tickets & RCAs<br/>JSON / CSV / JIRA .msg]
        B[MOPs & change records<br/>md / docx / pdf]
        C[Logs & command outputs]
    end

    subgraph Ingest["Ingest & structure"]
        D[Field mapper<br/>field_map.yaml<br/>+ privacy filter]
        E[Structure: node, release,<br/>MOP step, error, fix]
        F[Chunk by field<br/>symptom / root cause /<br/>resolution / learning / MOP step / log]
    end

    subgraph Index
        G[(ChromaDB<br/>bge-small embeddings<br/>+ metadata)]
        H[(BM25<br/>telecom tokenizer)]
        S[(SQLite<br/>records, tickets,<br/>notifications)]
    end

    subgraph Agent["Learning agent"]
        I[Fingerprint<br/>node, type, vendor, release,<br/>MOP, error & command signature]
        J{Missing node /<br/>MOP / release?}
        K[Plan searches]
        L[Tool calls]
        M[Rank: RRF + cross-encoder<br/>+ fingerprint bonus<br/>→ confidence 0-100]
        N{Confidence<br/>≥ threshold?}
        O[Cited draft →<br/>Mistral rewrite →<br/>citation check]
        P[Risk score]
    end

    subgraph Tools["Tools, RAG & APIs"]
        T1[search_by_symptom<br/>hybrid RAG]
        T2[search_by_mop_step]
        T3[node_history]
        T4[ticket API<br/>read / write learning]
        T5[notify_webhook<br/>Teams card]
    end

    A & B & C --> D --> E --> F --> G & H
    E --> S
    I --> J -- yes --> Q[Ask the engineer]
    J -- no --> K --> L --> M --> N
    N -- no, re-query ≤2x --> K
    N -- still no --> R[No verified match found]
    N -- yes --> O --> P --> X[Engineer reviews & decides]
    L <--> T1 & T2 & T3
    T1 <--> G & H
    P -- High risk --> T5
    X -- POST /feedback --> W[Verified learning<br/>written back] --> S & G & H
    W --> T4
```

## The three moments

| Moment | Endpoint | What the agent does |
|---|---|---|
| **Before** a planned LNI | `POST /recommend` `mode=pre_change` | Fingerprints the plan, asks for a missing node / MOP / release, checks node history, checks every MOP step for past failures, searches similar LNIs, scores risk, sends a Teams card if risk is High |
| **During** an incident | `POST /match` (search only) or `POST /recommend` `mode=incident` | Fingerprints symptoms / logs / commands, searches by symptom and exact error signature, re-queries with synonyms if confidence is low, returns cited root cause, fix and validation steps |
| **After** resolution | `POST /feedback` | Engineer confirms the fix (and who verified it); stored as a verified record, indexed immediately, ticket updated |

## Retrieval pipeline (`backend/app/rag/search.py`)

1. **Dense**: `BAAI/bge-small-en-v1.5` (Hugging Face, ONNX via fastembed) in ChromaDB, with metadata `where` filters (node type, vendor, release, MOP, field).
2. **Keyword**: BM25 with a tokenizer that keeps `CMG-12`, `MOP-UPG-04`, `7.11.1`, `%BGP-5-ADJCHANGE` intact.
3. **Fusion**: Reciprocal Rank Fusion pools the top 30 candidates from both.
4. **Rerank**: cross-encoder `ms-marco-MiniLM-L-6-v2` (configurable to `bge-reranker-base`).
5. **Record aggregation**: chunk scores roll up to the LNI record; log snippets map to their related LNI.
6. **Fingerprint bonus**: same node / node type / vendor / release / MOP / error signature. Applied proportionally to the remaining headroom, so it cannot lift a weak match over the threshold.
7. **Duplicate grouping**: reworded duplicates of the same root cause are shown once, marked "seen N×", and all their IDs are cited.

## Guardrails (`backend/app/agent/guardrails.py`)

- **Clarifying questions**: a pre-change check without a node, MOP or target release is blocked until the engineer answers. For an incident, the question is offered while the search runs anyway.
- **Threshold**: below the confidence threshold the agent says **"No verified match found"** and suggests no fix.
- **Citation check**: every LLM bullet must cite a retrieved record. Bullets that are uncited, or that cite an unknown ID, are dropped and shown as removed. If nothing survives, the deterministic cited draft is used.
- **Read-only**: tools with side effects (`write_learning`, `notify_webhook`) are blocked in the agent loop. Write-back only happens through `POST /feedback`, with a named human verifier.
- **Privacy**: customer, case-ID and person columns are dropped at ingestion and e-mail addresses are redacted. The LLM runs locally, so no data leaves the machine.
