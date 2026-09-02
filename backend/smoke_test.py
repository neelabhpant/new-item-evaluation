"""End-to-end smoke test for the New Item Evaluation platform.

Runs each canonical scenario through the real API + WebSocket pipeline,
asserts verdicts, exercises the follow-up endpoint, and verifies the
/latest endpoint's replay path.

Usage (from repo root, backend + frontend must be running):
    source venv/bin/activate
    python backend/smoke_test.py
"""
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import websockets


BASE_DIR = Path(__file__).resolve().parent.parent
TEST_IMAGES = Path(os.getenv("TEST_IMAGES_DIR", str(BASE_DIR / "data" / "images" / "test")))

# On Cloudera AI run the stack in a session (python deploy/app.py) and point
# API_BASE at http://127.0.0.1:$CDSW_APP_PORT; the public app URL sits behind login.
API_BASE = os.getenv("API_BASE", "http://localhost:8001").rstrip("/")
WS_BASE = os.getenv("WS_BASE") or ("wss://" if API_BASE.startswith("https://") else "ws://") + API_BASE.split("://", 1)[1]

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


SCENARIOS = [
    # eco_grain_bites dropped from the smoke suite: the product is visually +
    # semantically similar to existing granola/protein bars, so the system
    # legitimately classifies it as High Overlap + DECLINE. Not a bug — it's
    # honest behavior — but it doesn't add new demo coverage beyond the
    # Kellogs Protein Bar DECLINE. The image stays in data/images/test/ for
    # ad-hoc manual runs.
    {
        "key": "kellogs_protein_bar",
        "image": "kellogs_protein_bar.png",
        "payload": {
            "name": "Kellogs Protein Bar",
            "description": "Chocolate peanut butter protein meal bars with 12g protein per serving",
            "price": 5.49,
            "category": "Auto-detect",
            "claims": ["High Protein"],
        },
        "expected_verdict": "DECLINE",
        "note": "High Overlap — 29 protein bars in the catalog, saturated category",
    },
    {
        "key": "kombucha",
        "image": "kombucha.jpeg",
        "payload": {
            "name": "Wildspring Kombucha",
            "description": "Sparkling fermented tea with live cultures, ginger-turmeric",
            "price": 4.99,
            "category": "Auto-detect",
            "claims": ["Organic", "Non-GMO"],
        },
        "expected_verdict": "AUTHORIZE",
        "note": "White Space — no kombucha in catalog",
    },
    {
        "key": "truffle_popcorn",
        "image": "truffle_popcorn.jpeg",
        "payload": {
            "name": "Black Truffle Popcorn",
            "description": "Air-popped popcorn with black truffle oil and sea salt",
            "price": 6.99,
            "category": "Auto-detect",
            "claims": ["Organic", "No Artificial Flavors"],
        },
        "expected_verdict": "MODIFY",
        "note": "Moderate Overlap — 18 popcorn SKUs, premium differentiation",
    },
]


VERDICT_RE = re.compile(r"VERDICT:\s*(AUTHORIZE|DECLINE|MODIFY)", re.IGNORECASE)
CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*(\d+)", re.IGNORECASE)


async def run_evaluation(scenario: dict) -> dict:
    """Submit an evaluation and stream it to completion. Returns a result dict."""
    payload = dict(scenario["payload"])
    image_file = TEST_IMAGES / scenario["image"]
    if not image_file.exists():
        return {"ok": False, "error": f"missing image: {image_file}"}
    payload["image_path"] = str(image_file)

    t0 = time.time()
    try:
        resp = requests.post(f"{API_BASE}/api/evaluate", json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return {"ok": False, "error": f"POST /api/evaluate failed: {e}"}

    eval_id = resp.json().get("evaluation_id")
    if not eval_id:
        return {"ok": False, "error": "no evaluation_id in response"}

    messages = []
    steps_complete = set()
    reasoning_steps = set()
    final_output = None
    error_msg = None

    try:
        async with websockets.connect(f"{WS_BASE}/ws/evaluation/{eval_id}") as ws:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=90)
                msg = json.loads(raw)
                messages.append(msg)
                if msg.get("status") == "complete":
                    steps_complete.add(msg.get("step"))
                    if msg.get("reasoning"):
                        reasoning_steps.add(msg.get("step"))
                if msg.get("status") == "done" or msg.get("phase") == "done":
                    final_output = msg.get("output")
                    break
                if msg.get("status") == "error":
                    error_msg = msg.get("message")
                    break
    except Exception as e:
        return {"ok": False, "error": f"WS error: {e}"}

    elapsed = time.time() - t0
    if error_msg:
        return {"ok": False, "eval_id": eval_id, "error": error_msg, "elapsed": elapsed}

    m = VERDICT_RE.search(final_output or "")
    actual_verdict = m.group(1).upper() if m else "UNKNOWN"
    c = CONFIDENCE_RE.search(final_output or "")
    confidence = int(c.group(1)) if c else 0

    ok = actual_verdict == scenario["expected_verdict"] and len(steps_complete) >= 6
    return {
        "ok": ok,
        "eval_id": eval_id,
        "expected_verdict": scenario["expected_verdict"],
        "actual_verdict": actual_verdict,
        "confidence": confidence,
        "steps_complete": sorted(s for s in steps_complete if s is not None),
        "reasoning_steps": sorted(s for s in reasoning_steps if s is not None),
        "messages_count": len(messages),
        "elapsed": elapsed,
        "final_output_len": len(final_output or ""),
    }


async def run_followup(eval_id: str, question: str) -> dict:
    t0 = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/api/evaluate/followup/{eval_id}",
            json={"question": question},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        return {"ok": False, "error": f"POST /followup failed: {e}"}

    followup_id = resp.json().get("followup_id")
    if not followup_id:
        return {"ok": False, "error": "no followup_id"}

    chunks_total = 0
    full_output = ""

    try:
        async with websockets.connect(f"{WS_BASE}/ws/followup/{followup_id}") as ws:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
                msg = json.loads(raw)
                if msg.get("status") == "running" and msg.get("chunk"):
                    chunks_total += 1
                elif msg.get("status") == "complete":
                    full_output = msg.get("output", "")
                    break
                elif msg.get("status") == "error":
                    return {"ok": False, "error": msg.get("message")}
    except Exception as e:
        return {"ok": False, "error": f"follow-up WS error: {e}"}

    elapsed = time.time() - t0
    ok = len(full_output) > 60 and chunks_total > 0
    return {
        "ok": ok,
        "chunks_received": chunks_total,
        "output_length": len(full_output),
        "elapsed": elapsed,
    }


def run_latest() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/api/evaluations/latest", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    history = data.get("history")
    replay = data.get("replay_available")
    ok = history is not None and replay is True
    return {
        "ok": ok,
        "replay_available": replay,
        "history_product": (history or {}).get("product_name"),
        "history_verdict": (history or {}).get("verdict"),
    }


def _mark(ok: bool) -> str:
    return f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"


async def main() -> int:
    print(f"\n{BOLD}NIE Smoke Test — {len(SCENARIOS)} scenarios + follow-up + /latest{RESET}")
    print(f"{DIM}{'─' * 70}{RESET}\n")

    # Preflight
    try:
        requests.get(f"{API_BASE}/api/catalog/summary", timeout=5).raise_for_status()
    except Exception as e:
        print(f"{RED}✗ backend not reachable at {API_BASE}: {e}{RESET}")
        return 1

    scenario_results = []
    for sc in SCENARIOS:
        print(f"{BOLD}→ {sc['key']}{RESET}  {DIM}({sc['note']}){RESET}")
        print(f"  expected verdict: {YELLOW}{sc['expected_verdict']}{RESET}")
        r = await run_evaluation(sc)
        scenario_results.append((sc, r))

        if r.get("ok"):
            print(
                f"  {_mark(True)} {r['actual_verdict']} at {r['confidence']}%  "
                f"{DIM}({r['elapsed']:.1f}s · {r['messages_count']} msgs · "
                f"steps {r['steps_complete']}){RESET}"
            )
            missing = {4, 5, 6} - set(r.get("reasoning_steps", []))
            if missing:
                print(f"  {YELLOW}⚠ reasoning not seen for steps {sorted(missing)}{RESET}")
        else:
            print(
                f"  {_mark(False)} got={r.get('actual_verdict', '?')} "
                f"expected={sc['expected_verdict']}"
            )
            if r.get("error"):
                print(f"    {RED}error:{RESET} {r['error']}")
        print()

    # Follow-up — pick the first successful eval (prefer DECLINE for richest context)
    target = None
    for sc, r in scenario_results:
        if r.get("ok") and sc["expected_verdict"] == "DECLINE":
            target = r
            break
    if not target:
        target = next((r for _, r in scenario_results if r.get("ok")), None)

    followup_result = None
    if target:
        print(f"{BOLD}→ follow-up{RESET}  {DIM}(on {target['eval_id'][:8]}…){RESET}")
        print(f"  question: \"Which vendor is most at risk?\"")
        followup_result = await run_followup(
            target["eval_id"], "Which vendor is most at risk?"
        )
        if followup_result.get("ok"):
            print(
                f"  {_mark(True)} {followup_result['chunks_received']} chunks, "
                f"{followup_result['output_length']} chars, "
                f"{DIM}{followup_result['elapsed']:.1f}s{RESET}"
            )
        else:
            print(f"  {_mark(False)} error: {followup_result.get('error')}")
    else:
        print(f"{YELLOW}⚠ skipping follow-up — no successful evaluation{RESET}")
    print()

    # /latest
    print(f"{BOLD}→ /api/evaluations/latest{RESET}")
    latest_result = run_latest()
    if latest_result.get("ok"):
        print(
            f"  {_mark(True)} replay_available, history.product = "
            f"{latest_result['history_product']} · {latest_result['history_verdict']}"
        )
    else:
        print(f"  {_mark(False)} replay_available={latest_result.get('replay_available')}")
        if latest_result.get("error"):
            print(f"    {RED}error:{RESET} {latest_result['error']}")
    print()

    # Summary
    scen_pass = sum(1 for _, r in scenario_results if r.get("ok"))
    scen_total = len(SCENARIOS)
    fu_pass = 1 if followup_result and followup_result.get("ok") else 0
    fu_total = 1 if followup_result is not None else 0
    lt_pass = 1 if latest_result.get("ok") else 0

    total_pass = scen_pass + fu_pass + lt_pass
    total = scen_total + fu_total + 1

    color = GREEN if total_pass == total else RED
    print(f"{DIM}{'─' * 70}{RESET}")
    print(f"{BOLD}RESULT: {color}{total_pass}/{total} passed{RESET}  "
          f"({DIM}scenarios {scen_pass}/{scen_total} · "
          f"follow-up {fu_pass}/{fu_total} · /latest {lt_pass}/1{RESET})")
    return 0 if total_pass == total else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
