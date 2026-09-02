"""Follow-up question handler.

Re-uses the cached DataPackage + prior agent outputs from a completed evaluation
to answer a scoped follow-up question. Streams the answer back chunk-by-chunk.

Design commitment (from the design review): follow-ups do NOT spawn a new agent.
The same three agent roles are conceptually in play; we simply pipe the user's
question into a Merchandising-Lead-style synthesis prompt alongside the cached
DataPackage and prior agent outputs.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from typing import Any, Callable


SYSTEM_PROMPT = (
    "You are the Merchandising Lead for a grocery retailer. You have just completed "
    "a full evaluation of a new product submission alongside a Risk & Market Analyst "
    "and a Financial Projector. The three of you hold the full context for this "
    "evaluation. A merchant now has a follow-up question about THIS SPECIFIC "
    "evaluation. Answer it using the cached context below. "
    "Stay strictly scoped to this evaluation. Do not answer questions about "
    "unrelated vendors, categories, price forecasting, or portfolio audits. If the "
    "question is out of scope, respond with a short note explaining you can only "
    "answer questions about this evaluation and suggest a scoped reformulation. "
    "Your tone is direct, specific, evidence-based. Cite numbers from the cached "
    "data when relevant."
)


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[...truncated]"


def _build_prompt(raw_data: dict, tasks_output: list[str], question: str) -> str:
    sub = raw_data.get("submission", {})
    overlap = raw_data.get("overlap_classification", "")
    inferred = raw_data.get("inferred_category", "")
    saturation = raw_data.get("category_saturation", {})
    verdict = raw_data.get("predetermined_verdict", "")
    confidence = raw_data.get("predetermined_confidence", 0)

    risk_out = tasks_output[0] if len(tasks_output) > 0 else ""
    fin_out = tasks_output[1] if len(tasks_output) > 1 else ""
    synth_out = tasks_output[2] if len(tasks_output) > 2 else ""

    parts = [
        "=== EVALUATION CONTEXT ===",
        f"Product: {sub.get('name', '?')} ({sub.get('brand', '?')})",
        f"Submitted price: ${sub.get('price', 0):.2f}",
        f"Category submitted: {sub.get('category', '?')}",
        f"Inferred category: {inferred}",
        f"Overlap classification: {overlap}",
        f"Category saturation: {json.dumps(saturation)}",
        f"Final verdict: {verdict} (confidence {confidence}%)",
        "",
        "=== RISK & MARKET ANALYST OUTPUT ===",
        _truncate(risk_out),
        "",
        "=== FINANCIAL PROJECTOR OUTPUT ===",
        _truncate(fin_out),
        "",
        "=== MERCHANDISING LEAD OUTPUT ===",
        _truncate(synth_out),
        "",
        "=== MERCHANT'S FOLLOW-UP QUESTION ===",
        question,
        "",
        "Answer the question in 3-6 concise sentences. Use plain prose with specific numbers.",
    ]
    return "\n".join(parts)


def run_followup(
    evaluation_id: str,
    question: str,
    evaluations_store: dict[str, dict[str, Any]],
    send_msg: Callable[[dict], None],
) -> None:
    eval_state = evaluations_store.get(evaluation_id)
    if not eval_state or not eval_state.get("result"):
        send_msg({"status": "error", "message": "Evaluation not found or not yet complete."})
        return

    result = eval_state["result"]
    raw_data = result.get("data_package", {})
    tasks_output = result.get("tasks_output", [])

    prompt = _build_prompt(raw_data, tasks_output, question)
    try:
        from tools.llm_config import openai_client, settings

        client = openai_client()
        model_name = settings()["model"]
        stream = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=True,
            temperature=0.4,
        )
        buf: list[str] = []
        for chunk in stream:
            delta = None
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            if delta:
                buf.append(delta)
                send_msg({"status": "running", "chunk": delta})

        full = "".join(buf).strip()
        send_msg({"status": "complete", "output": full})
    except Exception as e:
        send_msg({"status": "error", "message": f"Follow-up failed: {e}"})
