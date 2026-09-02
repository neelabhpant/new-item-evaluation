# Deploying on Cloudera AI

This document describes how the New Item Evaluation Platform runs end-to-end on
Cloudera: the app in a **Cloudera AI Workbench Application**, the reasoning agents
on an open-weight model served by **Cloudera AI Inference**, the catalog vectors in
**OpenSearch**, and the retail tables as **Iceberg tables in the Cloudera Data Lake**
queried through **Cloudera Data Warehouse (Impala)**. Nothing in the stack depends
on a public cloud service, so the same layout runs on Cloudera on premises.

```
Cloudera AI Workbench project (this repo, on project storage)
│
├── Jobs (one-time bootstrap, chained)
│     nie-01-install-deps   pip (CPU torch), CLIP weights, OpenSearch bundle, Node + frontend build
│     nie-02-fetch-images   295 product images from Open Food Facts -> data/images/catalog/
│     nie-03-embed-catalog  CLIP ViT-B/32 image+text vectors -> data/catalog_embeddings.jsonl
│     nie-04-init-tables    Iceberg tables new_item_eval.* via Impala (products, sales, benchmarks, vendors)
│
└── Application "New Item Evaluation"  (deploy/app.py, 4 vCPU / 16 GB, port $CDSW_APP_PORT)
      ├─ OpenSearch 2.11 started inside the pod (127.0.0.1:9200), index loaded from the embeddings cache
      ├─ FastAPI + React build on one origin  (/api, /ws, /)
      ├─ CLIP embeds each submission on CPU
      ├─ k-NN search -> OpenSearch          (OPENSEARCH_URL; Data Hub cluster = config change)
      ├─ sales / vendor / benchmarks        -> Iceberg via CDW Impala (impyla, workload credentials)
      └─ 3 CrewAI agents + follow-up Q&A    -> Cloudera AI Inference endpoint (OpenAI-compatible)
                                              auth = workload JWT injected at /tmp/jwt
```

## 1. Prerequisites

| What | Where it comes from |
|---|---|
| Cloudera AI Workbench project with this repo as its files | Git import or upload |
| A running Cloudera AI Inference chat endpoint | AI Inference UI → Model Endpoints. Any OpenAI-compatible instruct model works; validated with `meta/llama-3.1-8b-instruct` (NIM) and `Qwen/Qwen2.5-7B-Instruct` (vLLM). Avoid "reasoning" models that emit chain-of-thought (e.g. Nemotron Super) because the agents' output is parsed line by line. |
| A CDW Impala Virtual Warehouse (or Data Hub Impala) the project can reach | Project → Data Connections lists them; `python deploy/check_endpoints.py` tests it |
| Workload password set for your CDP user | Management Console → User Management (CML exposes it as `WORKLOAD_PASSWORD`) |
| Outbound access from the workspace to PyPI, nodejs.org, artifacts.opensearch.org, openaipublic.azureedge.net, images.openfoodfacts.org | one-time bootstrap only |

## 2. Configure the project environment

Project Settings → Advanced → Environment Variables (secrets stay out of git):

```
LLM_PROVIDER=caii
LLM_BASE_URL=https://<ai-inference-domain>/namespaces/serving-default/endpoints/<endpoint>/v1
LLM_MODEL=<model id from <base_url>/models, e.g. meta/llama-3.1-8b-instruct>
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2048
# optional long-lived token (Knox API key); otherwise the pod's /tmp/jwt is used
#CDP_TOKEN=...

OPENSEARCH_MODE=embedded
OPENSEARCH_URL=http://127.0.0.1:9200
OPENSEARCH_INDEX=product-catalog

DB_BACKEND=impala
IMPALA_HOST=coordinator-<vw>.dw-<env>.cloudera.site     # from the JDBC URL in Data Connections
IMPALA_PORT=443
IMPALA_HTTP_PATH=cliservice                              # Data Hub: <cluster>/cdp-proxy-api/impala
IMPALA_USER=<cdp user>                                   # defaults to PROJECT_OWNER
IMPALA_PASSWORD=<workload password>                      # defaults to WORKLOAD_PASSWORD
IMPALA_DATABASE=new_item_eval

CLIP_CACHE_DIR=/home/cdsw/.cache/clip
CREWAI_TELEMETRY_OPT_OUT=true
OTEL_SDK_DISABLED=true
```

Notes on the NIM vs vLLM URL shapes: NIM endpoints expose `.../endpoints/<name>/v1`,
vLLM endpoints expose `.../endpoints/<name>/openai/v1`. Copy the base URL from the
endpoint's page in the AI Inference UI and strip `/chat/completions`.

## 3. Bootstrap and deploy

From a Workbench session (Python 3.10 or 3.11, PBJ Workbench or JupyterLab):

```bash
python deploy/cml_setup.py --run      # creates the 4 jobs + the application and starts job 01
```

Jobs run in order (each starts when its parent succeeds). Total time is dominated by
downloads on the first run (OpenSearch bundle ~1 GB, CLIP weights ~350 MB, torch CPU
wheel ~200 MB) and by CLIP on CPU (a few minutes for 295 products). Then start the
application from the Applications page; it becomes reachable at
`https://new-item-eval.<workbench-domain>` (login required unless created with `--public`).

Everything can also be run by hand inside a session, which is the fastest way to debug:

```bash
python deploy/install_deps.py
python scripts/fetch_images.py
python deploy/bootstrap_embed.py                 # CLIP -> data/catalog_embeddings.jsonl
python backend/data/init_db.py --backend impala  # Iceberg tables
python deploy/check_endpoints.py --list          # LLM, OpenSearch, Impala connectivity
python deploy/app.py                             # embedded OpenSearch + API + UI on $CDSW_APP_PORT
```

While `deploy/app.py` runs inside a session the UI is available through the session's
app preview (`https://<engine-id>.<workbench-domain>`), and the smoke test can be run
from a second terminal in the same session:

```bash
API_BASE=http://127.0.0.1:$CDSW_APP_PORT python backend/smoke_test.py
```

`GET /api/health` reports the state of every dependency (OpenSearch document count,
Impala row count, LLM provider/model and token expiry, frontend build, image count).

## 4. How each Cloudera service is used

### Cloudera AI Inference (agents and follow-up)
`backend/tools/llm_config.py` is the only place that knows about providers. With
`LLM_PROVIDER=caii` it builds a CrewAI `LLM(model="openai/<model>", base_url=..., api_key=...)`
for the three agents and an `openai.OpenAI(base_url=..., api_key=...)` client for the
streaming follow-up. The bearer token is resolved on every call in this order:
`LLM_API_KEY` → `CDP_TOKEN` → `/tmp/jwt` (the workload JWT Cloudera AI injects into pods)
→ `CML_JWT_FALLBACK_PATH` (default `.secrets/jwt.json` on project storage). Every file is
validated as an unexpired JWT before use: in this workspace the **Application** pod's
`/tmp/jwt` contained a Knox 404 HTML page, while session and job pods get a real token.
`deploy/save_session_token.py` copies a valid token to the fallback file (run it from a
session, or let the scheduled job `nie-05-refresh-token` do it every 6 hours); tokens
live about 10 days and `/api/health` reports `token_source`, validity and expiry. The
production alternative is `CDP_TOKEN` set to a long-lived Knox API key issued by an admin.
When no valid token exists the pipeline fails immediately at the first agent with an
explicit message instead of retrying.

The verdict (AUTHORIZE / MODIFY / DECLINE) and the financial scenario math are computed
deterministically in Python; the model only writes the reasoning prose, so swapping
models changes narrative quality, never the decision.

### OpenSearch (multimodal similarity)
`backend/tools/opensearch_conn.py` centralises URL, basic auth and TLS settings.

* **Embedded (default)** — `deploy/opensearch/embedded.py` downloads the official
  OpenSearch 2.11 bundle (JDK and k-NN plugin included) once onto project storage and
  starts it inside the application pod on `127.0.0.1:9200` with the security plugin
  disabled. Index data lives on the pod's local disk and is reloaded from
  `data/catalog_embeddings.jsonl` at every start (seconds; no CLIP needed).
* **External / Cloudera Data Hub** — set `OPENSEARCH_MODE=external`, `OPENSEARCH_URL`
  (the Knox-proxied endpoint), `OPENSEARCH_USER` / `OPENSEARCH_PASSWORD` (workload
  credentials) and `OPENSEARCH_CA_CERT`, then re-run job `nie-03-embed-catalog` which
  creates the index and bulk-loads it. The index mapping (`knn_vector`, 512 dims, HNSW,
  cosine, Lucene engine) and the similarity thresholds are unchanged, so verdicts stay
  identical as long as the cluster is OpenSearch 2.x with the k-NN plugin.

### Iceberg tables via Cloudera Data Warehouse (retail data)
`backend/data/init_db.py --backend impala` creates database `new_item_eval` and five
Iceberg tables (`products`, `sales_performance`, `category_benchmarks`,
`vendor_scorecard`, `evaluation_history`) with `CREATE TABLE ... STORED BY ICEBERG` and
seeds them with the same deterministic synthetic data the laptop DuckDB file has.
`backend/tools/db.py` runs the app's queries through `impyla` (HTTP transport, TLS,
LDAP with workload credentials, one shared connection with automatic reconnect).
Every completed evaluation is appended to `evaluation_history`, so the History tab is
backed by the lakehouse and the data is visible in Hue / CDW:

```sql
SELECT verdict, COUNT(*) FROM new_item_eval.evaluation_history GROUP BY verdict;
```

`DB_BACKEND=duckdb` keeps the original embedded file for laptop use.

### Cloudera AI Workbench (jobs and application)
`deploy/cml_setup.py` creates the jobs and the application with `cmlapi`, pinning one runtime
image (`CML_RUNTIME`, default PBJ JupyterLab Python 3.10) for everything. Packages installed
by job 01 land in `~/.local` on project storage and are shared by later jobs and the
application. Use the **same image** everywhere, not merely the same Python version: images
differ in preinstalled packages (the PBJ Workbench image lacks `pydantic`, for example), and
pip only installs what the image it runs in is missing.

## 5. Operations

**How the Workbench runs a script.** With PBJ runtimes, a job or application script is executed
inside an IPython kernel, chunk by chunk, from the project root. Consequences that shaped the
entry scripts in `deploy/` and `scripts/`:

* `__file__` is not defined, so every entry script resolves the repository root from the
  working directory (`_repo_root()` helper) instead of `Path(__file__)`.
* `sys.argv` belongs to the kernel, so command-line flags are parsed with `parse_known_args`.
* An uncaught exception ends the engine with exit code 1 and the message appears only in the
  application's Logs tab in the UI; `deploy/app.py` therefore also tees its output to
  `logs/app-<timestamp>.log` on project storage.
* The application and job APIs do not validate that the script exists at creation time; a
  missing script shows up as "Startup script ... does not exist" in the Logs tab.
* The kernel's asyncio loop is already running, so `uvicorn.run()` cannot be called from the
  script; `deploy/app.py` starts uvicorn as a child process and forwards its output.
* The engine itself listens on `<pod-ip>:$CDSW_APP_PORT` and forwards to localhost, so the
  server must bind `127.0.0.1:$CDSW_APP_PORT` (binding `0.0.0.0` fails with "address in use").


| Situation | What to do |
|---|---|
| LLM calls fail with 401, or the first agent stage errors with "No valid Cloudera workload token" | Token expired/invalid: run `python deploy/save_session_token.py` from a session (or the `nie-05-refresh-token` job), or set `CDP_TOKEN` |
| App log shows `Illegal header value b'Bearer <html>` / `Connection error` | The pod's `/tmp/jwt` is an HTML error page; the validated fallback file above fixes it |
| LLM calls fail with 404 / connection error | Endpoint stopped or URL wrong: `python deploy/check_endpoints.py --list` |
| First Impala query takes minutes | The Virtual Warehouse was suspended; it auto-resumes |
| Impala permission error on `CREATE DATABASE` | Ask the CDP admin for a Ranger policy on `new_item_eval`, or point `IMPALA_DATABASE` at a database you own |
| Application restart shows an empty catalog | `data/catalog_embeddings.jsonl` missing: re-run job `nie-03-embed-catalog` |
| Switching to a Data Hub OpenSearch | see "External / Cloudera Data Hub" above |
| Need to check whether Applications launch at all | create a throwaway Application with the stdlib-only `deploy/probe_app.py`; it writes `logs/probe.log` and serves "probe ok" |
| Running on premises | identical layout: Cloudera AI Inference endpoint URL, Impala host and workload credentials change; OpenSearch stays embedded or moves to a Data Hub cluster |
