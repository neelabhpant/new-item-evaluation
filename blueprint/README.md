# Cloudera Blueprint: Multimodal New Item Evaluation for Retail

Catalog and website fields live in [`METADATA.yaml`](METADATA.yaml). The AMP launch definition is [`.project-metadata.yaml`](../.project-metadata.yaml) at the repository root. This page is the business and onboarding view; the engineering detail is in the repository's [README.md](../README.md), [TECHNICAL.md](../TECHNICAL.md) and [DEPLOY_CLOUDERA.md](../DEPLOY_CLOUDERA.md).

## Table of Contents

- [Overview](#overview)
- [Demo](#demo)
- [Use Case](#use-case)
- [Key Features](#key-features)
- [Quickstart](#quickstart--guide)
- [Architecture / Software Components](#architecture--software-components)
- [Target Audience](#target-audience)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Hardware Requirements](#hardware-requirements)
- [Documentation](#documentation)
- [Data and License](#data-and-license)

## Overview

A grocery or CPG retailer receives new product proposals from suppliers and has to decide whether each one earns shelf space. This blueprint turns that decision into a repeatable pipeline on Cloudera AI. A supplier submits a product image, name, price, category and claims. The application embeds the image and text with CLIP, finds the most similar products already in the assortment with OpenSearch k-NN search, pulls sales, margin, vendor and category data from Iceberg tables in the Cloudera Data Lake, and then runs three CrewAI agents on an open-weight model served by Cloudera AI Inference to write the risk analysis, the financial projection and the recommendation. The verdict (AUTHORIZE, MODIFY or DECLINE) is computed by a fixed decision matrix in Python, not by the model, so results are consistent and auditable. Everything runs on Cloudera services with open-weight models; no public model API is called.

## Demo

NOT YET PROVIDED. A Reprise walkthrough has not been recorded. The end-to-end flow can be seen by launching the AMP (see Quickstart) or by running `backend/smoke_test.py` against a deployed instance, which drives three canonical submissions (a saturated protein bar category, a white-space kombucha, a premium popcorn) through the API and prints the verdicts.

## Use Case

**Problem.** Category managers evaluate hundreds of new item requests a year with spreadsheets, supplier decks and memory of what is already on the shelf. Two failure modes are common: authorizing a product that mostly cannibalizes an existing SKU, and declining a product that would have filled a real gap. Text descriptions do not capture how similar two products look to a shopper.

**What the blueprint does.** It answers three questions for every submission in well under a minute:

1. What in the current assortment does this product look like, visually and semantically?
2. What is the Year 1 financial impact after cannibalization, with best, expected and worst cases?
3. Should we authorize it, and if not, what would the supplier need to change?

**Business outcome.** Faster, evidence-backed new item decisions, a written rationale for every verdict, supplier feedback generated automatically for declined or conditional items, and an evaluation history stored in the lakehouse for later analysis.

## Key Features

- Image plus text similarity search over the existing catalog using CLIP embeddings and OpenSearch k-NN, so packaging and format matter, not only descriptions.
- Automatic category detection with a similarity-weighted vote, including a "new category" outcome when nothing in the catalog is close.
- Deterministic verdict matrix (overlap level times category saturation) that the LLM cannot override, which keeps decisions consistent and reviewable.
- Three sequential agents (risk and market analyst, financial modeler, recommendation synthesizer) that reason over pre-collected data, with no tool calls during reasoning.
- Financial scenarios and replacement-SKU suggestions that are validated against the sales data before they reach the merchant.
- Follow-up questions answered in a streaming chat scoped to the completed evaluation.
- Batch evaluation with a portfolio similarity matrix, catalog dashboard, merchant queue and supplier portal views.
- Evaluation history written to an Iceberg table, queryable from Hue or any Impala client.
- Runs entirely on Cloudera AI with open-weight models (Llama 3.1 8B validated, Qwen2.5 7B validated as an alternate). No GPU is required for the application itself.

## Quickstart / Guide

### Option A: launch as an AMP (recommended)

1. In a Cloudera AI Workbench, choose **New Project**, then **Initial Setup: AMPs**, and paste the repository URL `https://github.com/neelabhpant/new-item-evaluation`.
2. Click **Create Project**, then **Configure Project**. The values come from `.project-metadata.yaml`. Fill in:
   - `LLM_BASE_URL`: the OpenAI-compatible base URL of a running Cloudera AI Inference chat endpoint (NIM endpoints end in `/v1`, vLLM endpoints in `/openai/v1`).
   - `LLM_MODEL`: the model id reported by that endpoint, for example `meta/llama-3.1-8b-instruct`.
   - `IMPALA_HOST`: the coordinator host of a Cloudera Data Warehouse Impala Virtual Warehouse the project can reach.
   - `CDP_TOKEN` (optional but recommended): a long-lived workload token or Knox API key for the Application.
3. Launch. The AMP runs one install session, three bootstrap jobs (download 295 catalog images, compute CLIP embeddings, create and seed the Iceberg tables), saves a workload token for the Application, and starts the **New Item Evaluation** application. First-run time is dominated by downloads (OpenSearch bundle about 1 GB, CLIP weights about 350 MB, CPU torch wheel) and by CLIP on CPU, typically 20 to 40 minutes.
4. Open the application from the Applications page. `GET /api/health` on the application URL reports OpenSearch document count, Impala row count, LLM provider and token expiry.

### Option B: manual deployment from a session

From a Workbench session in the project (same runtime image as the application):

```bash
python deploy/cml_setup.py --run      # creates the jobs and the application with cmlapi, starts the bootstrap chain
python deploy/check_endpoints.py --list   # verifies the AI Inference endpoint, OpenSearch and Impala
```

Full environment variable reference and troubleshooting are in [DEPLOY_CLOUDERA.md](../DEPLOY_CLOUDERA.md).

### Option C: laptop

The repository [README.md](../README.md) describes running the same code on a laptop with OpenSearch in Docker, DuckDB instead of Impala, and any OpenAI-compatible server hosting an open-weight model.

## Architecture / Software Components

```
Supplier submission (image + name + price + category + claims)
        |
        v
Cloudera AI Workbench Application  (deploy/app.py, 4 vCPU / 16 GB, one pod, one origin)
  |-- React + Vite UI and FastAPI API on the same port (/, /api, /ws)
  |-- CLIP ViT-B/32 on CPU: one 512-dim vector per submission
  |-- OpenSearch 2.11 + k-NN plugin, embedded in the pod (127.0.0.1:9200)
  |       index rebuilt at start from data/catalog_embeddings.jsonl on project storage
  |-- impyla  ------------------------>  Cloudera Data Warehouse (Impala Virtual Warehouse)
  |                                        Iceberg tables new_item_eval.products, sales_performance,
  |                                        category_benchmarks, vendor_scorecard, evaluation_history
  |-- CrewAI (3 sequential agents) --->  Cloudera AI Inference chat endpoint (OpenAI-compatible)
  |       + streaming follow-up            open-weight model: Llama 3.1 8B (NIM) or Qwen2.5 7B (vLLM)
  |                                        auth: workload JWT or CDP_TOKEN
  v
Verdict matrix in Python -> AUTHORIZE / MODIFY / DECLINE + evidence, saved to evaluation_history

Bootstrap (Workbench Jobs / AMP tasks, run once):
  install deps -> fetch 295 catalog images (Open Food Facts) -> CLIP embeddings -> Iceberg tables
```

| Component | Role in the blueprint | Where in the code |
| --- | --- | --- |
| Cloudera AI Workbench | Hosts the project, runs the bootstrap as Jobs (or AMP tasks) and serves the app as an Application. Python packages live in `~/.local` on project storage and are shared by jobs and the application. | `deploy/cml_setup.py`, `deploy/app.py`, `.project-metadata.yaml` |
| Cloudera AI Inference | Serves the chat model the agents and the follow-up chat call through the OpenAI-compatible API. Bearer token resolved per call from `LLM_API_KEY`, `CDP_TOKEN`, the pod's `/tmp/jwt` or a validated fallback file. | `backend/tools/llm_config.py`, `backend/crew/agents.py`, `backend/pipeline/followup.py` |
| Cloudera Data Warehouse | Impala Virtual Warehouse over the Data Lake. Retail tables and the evaluation history are Iceberg tables created with `STORED BY ICEBERG`; queries use impyla with HTTP transport, TLS and LDAP workload credentials. | `backend/tools/db.py`, `backend/data/init_db.py`, `backend/tools/database_client.py` |
| OpenSearch 2.11 (k-NN) | Vector index of the catalog (512 dims, HNSW, cosine, Lucene engine). Runs as an embedded single-node process inside the Application pod: the official tarball with bundled JDK sits on project storage, the data directory is pod-local, the process binds 127.0.0.1 with the security plugin off. `OPENSEARCH_MODE=external` points the same client at any OpenSearch 2.x cluster with the k-NN plugin. | `deploy/opensearch/embedded.py`, `backend/tools/opensearch_conn.py`, `scripts/create_index.py` |
| CLIP ViT-B/32 | Open-weight image and text encoder from open-clip. Embeds each submission and, at bootstrap, every catalog product. CPU only. | `backend/tools/embedding_client.py`, `scripts/index_catalog.py` |
| CrewAI | Sequential process with three agents and no tools. Agents receive the pre-collected data as task context. Output is parsed line by line and post-processed deterministically. | `backend/crew/`, `backend/pipeline/orchestrator.py` |
| FastAPI + React | REST and WebSocket API, streaming progress to the UI, built frontend served from the same process. | `backend/main.py`, `frontend/` |

**What is durable and what is a cache.**

| Layer | Location | Durable |
| --- | --- | --- |
| Catalog metadata (295 products) | `data/catalog_products.json`, committed | yes |
| CLIP vectors | `data/catalog_embeddings.jsonl` on project storage, written by the embed job | yes |
| OpenSearch index | pod-local disk, rebuilt in seconds at every application start | no, rebuildable |
| Retail tables and evaluation history | Iceberg tables in the Data Lake via Impala | yes |

## Target Audience

- Solution architects and sales engineers who need a retail demo that exercises Workbench, AI Inference and Data Warehouse together.
- ML and application engineers building agentic workflows on Cloudera AI who want a reference for open-weight model integration, workload token handling, embedded vector search and Iceberg access from an Application.
- Category management and merchandising stakeholders evaluating AI-assisted new item review. Familiarity with assortment planning is enough to follow the UI.

Skill level: comfortable with Python and Cloudera AI Workbench projects. No model training and no GPU work is involved.

## Repository Structure

| Path | Description |
| --- | --- |
| `.project-metadata.yaml` | AMP definition: runtime, prompted environment variables, bootstrap tasks and the application |
| `blueprint/` | This page, `METADATA.yaml` and the catalog row for the Applied AI Blueprint sheet |
| `backend/main.py` | FastAPI app: evaluate, batch, follow-up, history, catalog and health endpoints; WebSocket streams |
| `backend/pipeline/` | Deterministic data collection, verdict matrix and orchestration, follow-up chat |
| `backend/crew/` | The three CrewAI agents, task prompts and sequential crew wiring |
| `backend/tools/` | Provider resolution for Cloudera AI Inference, OpenSearch connection and k-NN client, CLIP embedding, DuckDB or Impala backend |
| `backend/data/init_db.py` | Creates and seeds the retail tables (Iceberg via Impala, or DuckDB) with deterministic synthetic data |
| `backend/smoke_test.py` | End-to-end test: three scenarios, follow-up and replay through the live API |
| `deploy/` | Cloudera AI entry points: application launcher, job scripts, cmlapi setup, embedded OpenSearch, connectivity checks, frontend build |
| `scripts/` | Catalog bootstrap: download, categorize, fetch images, create index, embed and load |
| `frontend/` | React 19, TypeScript, Vite 8, Tailwind 4 user interface |
| `data/catalog_products.json` | Committed catalog metadata (Open Food Facts) that every other data artifact derives from |
| `data/images/test/` | Three test images used by the smoke test |
| `DEPLOY_CLOUDERA.md`, `TECHNICAL.md`, `README.md` | Deployment guide, technical reference, repository overview and laptop setup |
| `docker-compose.yml` | OpenSearch container for laptop use only |

## Prerequisites

- A Cloudera AI Workbench with the Python 3.10 JupyterLab Standard runtime available (the same image is used for the install session, the jobs and the application).
- A running Cloudera AI Inference chat endpoint. Any OpenAI-compatible instruct model works; validated with `meta/llama-3.1-8b-instruct` (NIM) and `Qwen/Qwen2.5-7B-Instruct` (vLLM). Avoid reasoning models that emit chain-of-thought, because agent output is parsed line by line.
- A Cloudera Data Warehouse Impala Virtual Warehouse the project can reach, and a Ranger policy that lets the user create the `new_item_eval` database (or an existing database set in `IMPALA_DATABASE`).
- A workload password set for the CDP user (Management Console, User Management). The platform injects it as `WORKLOAD_PASSWORD`, which is used for Impala LDAP authentication.
- For the Application's calls to AI Inference: either the workload JWT injected at `/tmp/jwt`, or `CDP_TOKEN` set to a long-lived token. In the reference workspace the Application pod's `/tmp/jwt` was not a valid token, so the launch also saves a token from the install session; `CDP_TOKEN` is the production choice.
- Outbound access from the workspace during bootstrap only: PyPI, download.pytorch.org, nodejs.org, artifacts.opensearch.org, openaipublic.azureedge.net (CLIP weights), images.openfoodfacts.org. At run time the application calls only the AI Inference endpoint, Impala and the embedded OpenSearch. The UI loads web fonts from fonts.googleapis.com and falls back to system fonts if that is blocked.
- Tools: git. Docker and Node are only needed for laptop use; the Cloudera path installs Node into the project.

## Hardware Requirements

| Deployment | Minimum |
| --- | --- |
| Launchable / demo (AMP) | Application 4 vCPU, 16 GB RAM. Bootstrap jobs up to 4 vCPU, 8 GB. About 4 GB of project storage (OpenSearch bundle 1 GB, Python packages 1.7 GB, CLIP cache 0.6 GB, Node 0.2 GB). No GPU. One evaluation takes 20 to 60 seconds, mostly LLM time. |
| Production / enterprise | Same CPU sizing per application replica; the application keeps evaluation state in process, so scale by running one replica per team. Size the Cloudera AI Inference endpoint (GPU) and the Impala Virtual Warehouse separately for the expected concurrency. Move OpenSearch to an external cluster (`OPENSEARCH_MODE=external`) when the catalog grows beyond what one pod should hold; the index mapping and thresholds do not change. |

## Documentation

- [README.md](../README.md): repository overview, API endpoints, verdict matrix, laptop setup.
- [DEPLOY_CLOUDERA.md](../DEPLOY_CLOUDERA.md): environment variables, job chain, how each Cloudera service is used, operations and troubleshooting.
- [TECHNICAL.md](../TECHNICAL.md): end-to-end technical reference for the pipeline, agents, WebSocket protocol and frontend.
- Cloudera docs: [Applied ML Prototypes project specification](https://docs.cloudera.com/machine-learning/cloud/applied-ml-prototypes/topics/ml-amp-project-spec.html), [Cloudera AI Inference](https://docs.cloudera.com/machine-learning/cloud/ai-inference/index.html), [Cloudera Data Warehouse](https://docs.cloudera.com/data-warehouse/cloud/index.html).

## Data and License

The catalog is 295 snack products from [Open Food Facts](https://world.openfoodfacts.org). Product metadata in `data/catalog_products.json` is available under the Open Database License (ODbL); product images, downloaded at bootstrap and not redistributed in this repository, are under Creative Commons Attribution-ShareAlike (CC BY-SA). Sales, margin, vendor and category benchmark figures are synthetic, generated with a fixed seed by `backend/data/init_db.py`, and do not describe any real retailer.

The code is licensed under the Apache License 2.0 (see [LICENSE](../LICENSE)).
