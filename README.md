# New Item Evaluation Platform

A sequential agentic workflow that evaluates new CPG / Grocery product proposals from suppliers against a retailer's existing assortment using multimodal (image + text) intelligence. A supplier submits a new product (images + data) and AI agents evaluate it step by step: visual similarity analysis, cannibalization risk, market context, financial projection, and a final recommendation.

The core differentiator: OpenSearch multimodal embeddings let the agents *see* what products look like, not just read their descriptions.

---

## Architecture

Hybrid pipeline: deterministic data collection + agentic reasoning.

```
User submission (image + name + price + category + claims)
        |
        v
PHASE 1 — Deterministic (2–3s, plain Python, no LLM)
  1. Generate CLIP embedding (ViT-B/32)
  2. OpenSearch k-NN visual similarity search
  3. Gather sales / category / vendor data from DuckDB
        |
        v
PHASE 2 — Agentic reasoning (CrewAI, sequential)
  4. Risk & Market Analyst        -> cannibalization + market timing
  5. Financial Modeler            -> revenue + margin + scenarios
  6. Recommendation Synthesizer   -> AUTHORIZE / MODIFY / DECLINE
        |
        v
Deterministic verdict engine resolves the final call
based on overlap classification + category saturation.
```

The final verdict is **not** chosen by an LLM — it is computed by a decision matrix in `backend/pipeline/orchestrator.py:compute_verdict()`. Agent 3 synthesizes evidence to support the predetermined verdict so decisions stay consistent and auditable.

---

## Tech stack

- Python 3.11+, FastAPI, uvicorn
- CrewAI for agent orchestration (sequential)
- Open-weight LLM on Cloudera AI Inference (Llama 3.1 8B) for agent reasoning via CrewAI; OpenAI GPT-4o-mini as the laptop alternative (`LLM_PROVIDER`)
- React 18 + TypeScript + Vite + Tailwind v4
- OpenSearch 2.11 (Docker on a laptop; embedded in the Cloudera AI application pod, or a Cloudera Data Hub cluster)
- Retail tables as Iceberg in the Cloudera Data Lake via Cloudera Data Warehouse Impala (`DB_BACKEND=impala`); DuckDB on a laptop
- CLIP (ViT-B/32 via open-clip-torch) for multimodal embeddings
- WebSocket streaming for real-time UI updates

---

## Deploy on Cloudera AI

The platform runs end-to-end on Cloudera: a Cloudera AI Workbench Application serves the app, the agents call an open-weight model on Cloudera AI Inference, OpenSearch runs embedded in the application pod (or on a Data Hub cluster), and the retail tables are Iceberg tables queried through Cloudera Data Warehouse Impala. Bootstrap is a chain of four Workbench Jobs.

```bash
python deploy/cml_setup.py --run     # from a Workbench session: creates jobs + application, starts bootstrap
```

See [DEPLOY_CLOUDERA.md](DEPLOY_CLOUDERA.md) for configuration, the job chain, and how each Cloudera service is used.

## Getting started (laptop)

### Prerequisites

- Docker Desktop (for OpenSearch)
- Python 3.11+
- Node.js 18+

### 1. Configure secrets

```bash
cp .env.example .env
# laptop: set LLM_PROVIDER=openai + OPENAI_API_KEY, OPENSEARCH_MODE=external, DB_BACKEND=duckdb
```

### 2. Start OpenSearch

```bash
docker compose up -d
curl http://localhost:9200   # verify
```

### 3. Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. One-time bootstrap (~10–15 minutes)

Populates the OpenSearch index and seeds DuckDB. Run after `docker compose up -d` and before starting the backend.

```bash
# 1. Download the 295 catalog images referenced by data/catalog_products.json
#    (scripts/download_catalog.py + assign_categories.py rebuild the catalog from scratch instead)
python scripts/fetch_images.py

# 2. Generate CLIP embeddings (cached in data/catalog_embeddings.jsonl) and bulk-load
#    the product-catalog index (created automatically; dim=512, hnsw, cosinesimil)
python scripts/index_catalog.py

# 3. Seed the retail tables (DuckDB here; --backend impala for Iceberg on Cloudera)
python backend/data/init_db.py --backend duckdb
```

Verify the OpenSearch index is populated:

```bash
curl http://localhost:9200/product-catalog/_count
```

### 5. Run the backend

```bash
cd backend && python -m uvicorn main:app --port 8001
```

### 6. Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api and /ws to backend:8001
# or build once (deploy/build_frontend.sh) and let the backend serve frontend/dist itself
```

### 7. Smoke test

```bash
source venv/bin/activate
python backend/smoke_test.py
```

Exercises the full pipeline end-to-end (3 canonical scenarios + follow-up + replay). Expect 5/5 passing in ~90 seconds.

---

## Repository layout

```
.
├── docker-compose.yml          # OpenSearch container (laptop)
├── .env.example                # Template for required env vars
├── DEPLOY_CLOUDERA.md          # Cloudera AI deployment guide
├── deploy/
│   ├── app.py                  # Cloudera AI Application entry (embedded OpenSearch + API + UI)
│   ├── cml_setup.py            # Creates the Workbench jobs + application via cmlapi
│   ├── install_deps.py         # Job 01: pip / CLIP weights / OpenSearch bundle / frontend build
│   ├── bootstrap_embed.py      # Job 03: CLIP embeddings cache (+ remote OpenSearch load)
│   ├── check_endpoints.py      # Connectivity checks for AI Inference, OpenSearch, Impala
│   ├── build_frontend.sh       # Node install + npm build without a system Node
│   └── opensearch/embedded.py  # OpenSearch running inside a Cloudera AI pod
├── backend/
│   ├── main.py                 # FastAPI app + WebSocket endpoints (port 8001)
│   ├── smoke_test.py
│   ├── requirements.txt
│   ├── pipeline/
│   │   ├── data_collector.py   # Deterministic Phase 1
│   │   ├── orchestrator.py     # Runs collector + crew + verdict engine
│   │   └── followup.py         # Post-verdict Q&A streaming
│   ├── crew/
│   │   ├── agents.py           # 3 CrewAI agents (no tools)
│   │   ├── tasks.py            # Task builders with REASONING: field
│   │   └── crew.py             # Sequential crew wiring
│   ├── tools/
│   │   ├── llm_config.py       # Cloudera AI Inference / OpenAI provider resolution
│   │   ├── opensearch_conn.py  # OpenSearch URL / auth / TLS (embedded, Data Hub, docker)
│   │   ├── opensearch_client.py
│   │   ├── embedding_client.py
│   │   ├── db.py               # DuckDB or Impala (Iceberg) query backend
│   │   └── database_client.py
│   └── data/
│       └── init_db.py          # Seed retail tables (DuckDB or Iceberg via Impala)
├── frontend/                   # React + Vite + Tailwind v4
└── data/
    └── catalog_products.json   # Catalog metadata (consumed by init_db.py)
```

---

## API endpoints

```
POST   /api/evaluate                          # Submit product -> { evaluation_id }
WS     /ws/evaluation/{evaluation_id}         # Stream pipeline progress

POST   /api/evaluate/followup/{evaluation_id} # { question } -> { followup_id }
WS     /ws/followup/{followup_id}             # Stream answer chunks

GET    /api/evaluations/latest                # Replay last run
GET    /api/evaluations                       # History
GET    /api/evaluations/stats                 # Aggregate stats
POST   /api/evaluate/batch                    # Batch evaluation
WS     /ws/batch/{batch_id}                   # Batch progress
GET    /api/products/{sku}                    # Product details
GET    /api/catalog/summary                   # Category counts
GET    /api/catalog/products                  # Full catalog listing
GET    /api/images/{filename}                 # Static product images
GET    /api/health                            # OpenSearch / Impala / LLM / frontend status
```

---

## Verdict matrix

|                              | Category Full (≥15 SKUs) | Category Has Room (<15 SKUs) |
|------------------------------|--------------------------|------------------------------|
| **High Overlap (>0.88)**     | DECLINE (90%)            | MODIFY (75%)                 |
| **Moderate (0.82–0.88)**     | MODIFY (72%)             | AUTHORIZE (80%)              |
| **White Space (<0.82)**      | AUTHORIZE (85%)          | AUTHORIZE (85%)              |
| **New Category**             | AUTHORIZE (82%)          | AUTHORIZE (82%)              |

Computed in `backend/pipeline/orchestrator.py:compute_verdict()`.

---

## Notes

- Revenue in DuckDB is computed as `weekly_units * price * 52 * noise_factor` (0.85–1.15) so price / velocity / revenue stay internally consistent.
- Agent 2's financial projections are post-processed to enforce Best = Expected × 1.20 and Worst = Expected × 0.70, preventing identical scenario values.
- Auto-detect category uses similarity-weighted voting across cross-category top-20 results. Threshold `MIN_CATEGORY_SIMILARITY = 0.86` — below that the product is classified as **New Category**.
- CrewAI agents receive the pre-collected DataPackage as task context. They do **not** call tools, eliminating tool-call latency and failure modes.
