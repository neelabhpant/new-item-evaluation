import asyncio
import base64
import logging
import sys
import tempfile
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.orchestrator import run_evaluation
from pipeline.followup import run_followup
from tools.database_client import get_catalog_summary, get_all_products, get_evaluations, get_evaluation_stats

app = FastAPI(title="New Item Evaluation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

evaluations: dict[str, dict[str, Any]] = {}
last_completed_evaluation_id: str | None = None


@app.on_event("startup")
async def _startup():
    from data.init_db import ensure_evaluation_history
    ensure_evaluation_history()


class EvaluateRequest(BaseModel):
    name: str
    description: str
    price: float
    category: str
    claims: str | list[str]
    image: str | None = None
    image_path: str | None = None


class BatchItem(BaseModel):
    name: str
    description: str
    price: float
    category: str
    claims: str | list[str]
    image: str | None = None
    image_path: str | None = None


class BatchRequest(BaseModel):
    products: list[BatchItem]


batches: dict[str, dict[str, Any]] = {}
followups: dict[str, dict[str, Any]] = {}


class FollowupRequest(BaseModel):
    question: str


def _run_followup_bg(
    evaluation_id: str,
    followup_id: str,
    question: str,
    loop: asyncio.AbstractEventLoop,
) -> None:
    queue: asyncio.Queue = followups[followup_id]["queue"]

    def send(msg: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    try:
        run_followup(evaluation_id, question, evaluations, send)
    except Exception as e:
        logging.error("Follow-up error: %s\n%s", e, traceback.format_exc())
        send({"status": "error", "message": str(e)})


def _run_pipeline(
    evaluation_id: str,
    image_path: str,
    name: str,
    description: str,
    price: float,
    category: str,
    claims: list[str],
    brand: str,
    loop: asyncio.AbstractEventLoop,
) -> None:
    queue: asyncio.Queue = evaluations[evaluation_id]["queue"]

    def send_msg(msg: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    try:
        result = run_evaluation(
            image_path=image_path,
            name=name,
            description=description,
            price=price,
            category=category,
            claims=claims,
            brand=brand,
            send_msg=send_msg,
        )
        evaluations[evaluation_id]["result"] = result
        global last_completed_evaluation_id
        last_completed_evaluation_id = evaluation_id
    except Exception as e:
        logging.error("Pipeline error: %s\n%s", e, traceback.format_exc())
        send_msg({
            "phase": "done",
            "step": 1,
            "step_name": "Error",
            "agent": "system",
            "status": "error",
            "message": str(e),
            "output": None,
        })


@app.post("/api/evaluate")
async def evaluate(request: EvaluateRequest) -> JSONResponse:
    evaluation_id = str(uuid.uuid4())

    image_path = request.image_path
    if request.image and not image_path:
        suffix = ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(base64.b64decode(request.image))
        tmp.close()
        image_path = tmp.name

    if not image_path:
        return JSONResponse(
            status_code=400,
            content={"error": "Either image (base64) or image_path must be provided"},
        )

    claims = request.claims
    if isinstance(claims, str):
        claims = [c.strip() for c in claims.split(",") if c.strip()]

    evaluations[evaluation_id] = {
        "queue": asyncio.Queue(),
        "result": None,
    }

    loop = asyncio.get_event_loop()
    thread = threading.Thread(
        target=_run_pipeline,
        args=(
            evaluation_id,
            image_path,
            request.name,
            request.description,
            request.price,
            request.category,
            claims,
            "Unknown",
            loop,
        ),
        daemon=True,
    )
    thread.start()

    return JSONResponse(content={"evaluation_id": evaluation_id})


@app.websocket("/ws/evaluation/{evaluation_id}")
async def evaluation_ws(websocket: WebSocket, evaluation_id: str):
    await websocket.accept()

    if evaluation_id not in evaluations:
        await websocket.send_json({"error": "Evaluation not found"})
        await websocket.close()
        return

    queue: asyncio.Queue = evaluations[evaluation_id]["queue"]

    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=600)
            await websocket.send_json(msg)
            if msg.get("status") in ("done", "error"):
                break
    except asyncio.TimeoutError:
        await websocket.send_json({"status": "error", "message": "Evaluation timed out"})
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


@app.post("/api/evaluate/followup/{evaluation_id}")
async def create_followup(evaluation_id: str, request: FollowupRequest) -> JSONResponse:
    if evaluation_id not in evaluations:
        return JSONResponse(status_code=404, content={"error": "Evaluation not found"})
    if not evaluations[evaluation_id].get("result"):
        return JSONResponse(
            status_code=409,
            content={"error": "Evaluation is not yet complete. Try again after the verdict lands."},
        )

    followup_id = str(uuid.uuid4())
    followups[followup_id] = {
        "queue": asyncio.Queue(),
        "evaluation_id": evaluation_id,
    }

    loop = asyncio.get_event_loop()
    thread = threading.Thread(
        target=_run_followup_bg,
        args=(evaluation_id, followup_id, request.question, loop),
        daemon=True,
    )
    thread.start()
    return JSONResponse(content={"followup_id": followup_id})


@app.websocket("/ws/followup/{followup_id}")
async def followup_ws(websocket: WebSocket, followup_id: str):
    await websocket.accept()

    if followup_id not in followups:
        await websocket.send_json({"status": "error", "message": "Follow-up not found"})
        await websocket.close()
        return

    queue: asyncio.Queue = followups[followup_id]["queue"]

    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=120)
            await websocket.send_json(msg)
            if msg.get("status") in ("complete", "error"):
                break
    except asyncio.TimeoutError:
        await websocket.send_json({"status": "error", "message": "Follow-up timed out"})
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


@app.get("/api/products/{sku}")
async def get_product(sku: str) -> JSONResponse:
    import requests as req
    try:
        resp = req.get(
            f"http://localhost:9200/product-catalog/_doc/{sku}",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            source = data.get("_source", {})
            source.pop("embedding", None)
            return JSONResponse(content=source)
        return JSONResponse(status_code=404, content={"error": f"Product {sku} not found"})
    except req.exceptions.ConnectionError:
        return JSONResponse(status_code=503, content={"error": "OpenSearch is not available"})


@app.get("/api/catalog/summary")
async def catalog_summary() -> JSONResponse:
    return JSONResponse(content=get_catalog_summary())


@app.get("/api/catalog/products")
async def catalog_products(category: str | None = None) -> JSONResponse:
    return JSONResponse(content=get_all_products(category))


def _run_batch(
    batch_id: str,
    products: list[dict],
    loop: asyncio.AbstractEventLoop,
) -> None:
    queue: asyncio.Queue = batches[batch_id]["queue"]

    def send(msg: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    results = []
    total = len(products)

    for idx, item in enumerate(products):
        send({
            "type": "product_start",
            "index": idx,
            "total": total,
            "product_name": item["name"],
        })

        try:
            result = run_evaluation(
                image_path=item["image_path"],
                name=item["name"],
                description=item["description"],
                price=item["price"],
                category=item["category"],
                claims=item["claims"],
                brand="Unknown",
                send_msg=None,
            )
            results.append({"index": idx, "name": item["name"], "result": result["result"]})
            send({
                "type": "product_complete",
                "index": idx,
                "total": total,
                "product_name": item["name"],
                "result_preview": result["result"][:500],
            })
        except Exception as e:
            results.append({"index": idx, "name": item["name"], "error": str(e)})
            send({
                "type": "product_error",
                "index": idx,
                "total": total,
                "product_name": item["name"],
                "error": str(e),
            })

    # Compute pairwise CLIP similarity between submitted products
    embeddings = batches[batch_id].get("embeddings", [])
    matrix: list[list[float]] = []
    if len(embeddings) >= 2:
        import numpy as np
        emb_array = np.array(embeddings)
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normed = emb_array / norms
        sim = (normed @ normed.T).tolist()
        matrix = [[round(v, 4) for v in row] for row in sim]

    send({
        "type": "batch_done",
        "total": total,
        "results": results,
        "similarity_matrix": matrix,
    })


@app.post("/api/evaluate/batch")
async def evaluate_batch(request: BatchRequest) -> JSONResponse:
    batch_id = str(uuid.uuid4())

    items = []
    for item in request.products:
        image_path = item.image_path
        if item.image and not image_path:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(base64.b64decode(item.image))
            tmp.close()
            image_path = tmp.name
        if not image_path:
            continue
        claims = item.claims
        if isinstance(claims, str):
            claims = [c.strip() for c in claims.split(",") if c.strip()]
        items.append({
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "category": item.category,
            "claims": claims,
            "image_path": image_path,
        })

    if not items:
        return JSONResponse(status_code=400, content={"error": "No valid products provided"})

    batches[batch_id] = {"queue": asyncio.Queue(), "embeddings": []}

    loop = asyncio.get_event_loop()
    thread = threading.Thread(target=_run_batch, args=(batch_id, items, loop), daemon=True)
    thread.start()

    return JSONResponse(content={"batch_id": batch_id, "count": len(items)})


@app.websocket("/ws/batch/{batch_id}")
async def batch_ws(websocket: WebSocket, batch_id: str):
    await websocket.accept()
    if batch_id not in batches:
        await websocket.send_json({"error": "Batch not found"})
        await websocket.close()
        return

    queue: asyncio.Queue = batches[batch_id]["queue"]
    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=1800)
            await websocket.send_json(msg)
            if msg.get("type") == "batch_done":
                break
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Batch timed out"})
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


@app.get("/api/evaluations")
async def list_evaluations(limit: int = 50, offset: int = 0) -> JSONResponse:
    return JSONResponse(content=get_evaluations(limit, offset))


@app.get("/api/evaluations/stats")
async def evaluation_stats() -> JSONResponse:
    return JSONResponse(content=get_evaluation_stats())


@app.get("/api/evaluations/latest")
async def latest_evaluation() -> JSONResponse:
    """Return the most recent evaluation_history row + the in-memory result
    if that evaluation is still cached in the `evaluations` dict. Used by
    the empty-state Last Session Replay strip."""
    # DuckDB read-only connections occasionally conflict with in-flight write
    # connections from save_evaluation. Retry once on failure, then fall back.
    history_row = None
    for attempt in range(2):
        try:
            rows = get_evaluations(limit=1, offset=0)
            history_row = rows[0] if rows else None
            break
        except Exception as e:
            if attempt == 0:
                import time
                time.sleep(0.25)
                continue
            logging.warning("Failed to read evaluation history for /latest: %s", e)

    result_payload = None
    if last_completed_evaluation_id and last_completed_evaluation_id in evaluations:
        eval_state = evaluations[last_completed_evaluation_id]
        cached = eval_state.get("result")
        if cached:
            from pipeline.orchestrator import extract_reasoning

            raw_data = cached.get("data_package", {})
            tasks_output = cached.get("tasks_output", [])
            agent_ids = ["risk", "fin", "synth"]
            reasonings = [
                extract_reasoning(agent_ids[i], tasks_output[i] if i < len(tasks_output) else "", raw_data)
                for i in range(3)
            ]
            result_payload = {
                "evaluation_id": last_completed_evaluation_id,
                "data_package": raw_data,
                "tasks_output": tasks_output,
                "reasonings": reasonings,
                "final_output": cached.get("result", ""),
            }

            # If the history query failed, synthesize a history row from the
            # cached submission so the Last Session strip still renders.
            if history_row is None:
                sub = raw_data.get("submission", {})
                import re as _re
                m = _re.search(r"VERDICT:\s*(AUTHORIZE|DECLINE|MODIFY)", cached.get("result", ""))
                c = _re.search(r"CONFIDENCE:\s*(\d+)", cached.get("result", ""))
                history_row = {
                    "id": last_completed_evaluation_id[:8],
                    "timestamp": "",
                    "product_name": sub.get("name", ""),
                    "brand": sub.get("brand", ""),
                    "category": sub.get("category", ""),
                    "inferred_category": raw_data.get("inferred_category", ""),
                    "price": sub.get("price", 0),
                    "claims": ", ".join(sub.get("claims", [])) if isinstance(sub.get("claims"), list) else str(sub.get("claims", "")),
                    "verdict": m.group(1).upper() if m else "",
                    "confidence": int(c.group(1)) if c else 0,
                    "overlap_classification": raw_data.get("overlap_classification", ""),
                    "expected_revenue": 0,
                    "max_similarity": 0,
                    "risk_rating": "",
                    "image_path": sub.get("image_path", ""),
                }

    return JSONResponse(content={
        "history": history_row,
        "replay_available": result_payload is not None,
        "result": result_payload,
    })


@app.get("/api/images/{filename}")
async def get_image(filename: str) -> FileResponse:
    image_path = BASE_DIR / "data" / "images" / "catalog" / filename
    if image_path.exists():
        return FileResponse(str(image_path), media_type="image/jpeg")
    return JSONResponse(status_code=404, content={"error": "Image not found"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
