# Quick Start (laptop)

For Cloudera AI see [DEPLOY_CLOUDERA.md](DEPLOY_CLOUDERA.md).

## Prerequisites

- Docker running (for OpenSearch)
- Python 3.11+ with venv
- Node.js 22.12+ (Vite 8)

## Start OpenSearch

```bash
docker compose up -d
```

Verify: `curl http://localhost:9200`

## Start Backend

```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8001
```

Runs on http://localhost:8001

## Start Frontend

```bash
cd frontend
npm install   # first time only
npm run dev
```

Runs on http://localhost:5173

## Seed DuckDB (first time)

```bash
source venv/bin/activate
python backend/data/init_db.py --backend duckdb
```

## Kill Servers

```bash
# Kill backend
lsof -ti:8001 | xargs kill -9

# Kill frontend
lsof -ti:5173 | xargs kill -9

# Stop OpenSearch
docker compose down
```

## Ports

| Service     | Port |
|-------------|------|
| Backend     | 8001 |
| Frontend    | 5173 |
| OpenSearch  | 9200 |
