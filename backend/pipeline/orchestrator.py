import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.data_collector import collect_evaluation_data

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "crew"))
from crew import create_evaluation_crew, AGENT_NAMES


def compute_verdict(raw_data: dict) -> tuple[str, int]:
    """Deterministic verdict from overlap classification and category fullness.

    Decision matrix:
                          | Category Full (>=15 SKUs) | Has Room (<15 SKUs)
    ----------------------|---------------------------|---------------------
    High Overlap (>0.88)  | DECLINE  (90%)            | MODIFY   (75%)
    Moderate (0.82-0.88)  | MODIFY   (72%)            | AUTHORIZE (80%)
    White Space (<0.82)   | AUTHORIZE (85%)           | AUTHORIZE (85%)
    New Category          | AUTHORIZE (82%)           | AUTHORIZE (82%)
    """
    overlap = raw_data.get("overlap_classification", "")
    is_full = raw_data.get("category_saturation", {}).get("category_is_full", False)
    is_new = raw_data.get("is_new_category", False)

    if is_new:
        return ("AUTHORIZE", 82)
    if overlap == "White Space":
        return ("AUTHORIZE", 85)
    if overlap == "High Overlap":
        return ("DECLINE", 90) if is_full else ("MODIFY", 75)
    if overlap == "Moderate Overlap":
        return ("MODIFY", 72) if is_full else ("AUTHORIZE", 80)
    return ("AUTHORIZE", 70)


def _fix_financial_scenarios(output: str, price: float) -> str:
    """Ensure Best/Expected/Worst cases are distinct and mathematically consistent."""
    expected_m = re.search(r"EXPECTED:\s*\$?([\d,]+(?:\.\d+)?)", output)
    if not expected_m:
        return output

    expected_val = float(expected_m.group(1).replace(",", ""))
    if expected_val <= 0:
        return output

    best_val = expected_val * 1.20
    worst_val = expected_val * 0.70

    output = re.sub(
        r"BEST_CASE:\s*\$?[\d,]+(?:\.\d+)?[^\n]*",
        f"BEST_CASE: ${best_val:,.0f} annual revenue",
        output,
    )
    output = re.sub(
        r"EXPECTED:\s*\$?[\d,]+(?:\.\d+)?[^\n]*",
        f"EXPECTED: ${expected_val:,.0f} annual revenue",
        output,
    )
    output = re.sub(
        r"WORST_CASE:\s*\$?[\d,]+(?:\.\d+)?[^\n]*",
        f"WORST_CASE: ${worst_val:,.0f} annual revenue",
        output,
    )
    return output


def _extract_field(text: str, field_name: str) -> str:
    """Extract a labeled field value from Agent 3's structured output."""
    match = re.search(rf"{field_name}:\s*(.+?)(?:\n|$)", text)
    return match.group(1).strip() if match else ""


_REASONING_RE = re.compile(
    r"^REASONING:\s*(.+?)(?=\n[A-Z][A-Z_0-9]{2,}:|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Leading-prose fallback: some agents omit the REASONING: label and just emit
# prose before the first structured FIELDNAME: line. Treat that as reasoning.
_LEADING_PROSE_RE = re.compile(
    r"\A(.+?)(?=\n[A-Z][A-Z_0-9]{2,}:|\Z)",
    re.DOTALL,
)

_FIELDNAME_RE = re.compile(r"^[A-Z][A-Z_0-9]{2,}:")


def _clean_prose(prose: str) -> str:
    """Strip placeholder brackets and cap length."""
    prose = prose.strip()
    if prose.startswith("[") and prose.endswith("]"):
        prose = prose[1:-1].strip()
    if len(prose) > 600:
        cut = prose.rfind(".", 0, 600)
        prose = prose[: cut + 1] if cut > 200 else prose[:600]
    return prose


def extract_reasoning(agent_id: str, raw_output: str, raw_data: dict) -> str:
    """Pull the reasoning prose from an agent's output. First try an explicit
    `REASONING:` block. If the agent emitted conversational prose without the
    label, fall back to capturing the leading text before the first structured
    field. Final fallback is a deterministic sentence synthesized from the
    DataPackage.
    """
    if raw_output:
        # 1. Explicit REASONING: label
        m = _REASONING_RE.search(raw_output)
        if m:
            prose = _clean_prose(m.group(1))
            if len(prose) >= 40:
                return prose

        # 2. Leading prose before the first FIELDNAME: line
        stripped = raw_output.lstrip()
        m2 = _LEADING_PROSE_RE.search(stripped)
        if m2:
            prose = _clean_prose(m2.group(1))
            # Only accept if it's actually prose, not a structured field
            if len(prose) >= 40 and not _FIELDNAME_RE.match(prose):
                return prose

    return _fallback_reasoning(agent_id, raw_data)


def _similar_prose(a: str, b: str, threshold: float = 0.8) -> bool:
    """True when two reasoning strings are (near) duplicates."""
    if not a or not b:
        return False
    import difflib

    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def _fallback_reasoning(agent_id: str, raw_data: dict) -> str:
    """Deterministic reasoning synthesized from the DataPackage when the
    agent's output lacks a parseable REASONING: block."""
    sub = raw_data.get("submission", {})
    cat = raw_data.get("inferred_category", "the category")
    overlap = raw_data.get("overlap_classification", "")
    if agent_id == "risk":
        n = len(raw_data.get("enriched_products", []))
        return (
            f"I scanned {n} similar products in {cat}. The overlap reads as "
            f"{overlap.lower()}. That shapes where cannibalization risk sits."
        )
    if agent_id == "fin":
        price = sub.get("price", 0)
        return (
            f"At ${price:.2f}, the Year-1 math depends on whether we replace any "
            f"declining SKUs. I'll walk through the best, expected, and worst scenarios now."
        )
    if agent_id == "synth":
        v = raw_data.get("predetermined_verdict", "")
        c = raw_data.get("predetermined_confidence", 0)
        return (
            f"Synthesizing across all three agents, the verdict lands at {v} with "
            f"{c}% confidence. Here's the evidence."
        )
    return ""


STEP_NAMES = [
    "Submission Processed",
    "Visual Similarity Search",
    "Data Collection",
    "Risk & Market Analysis",
    "Financial Projection",
    "Recommendation",
]


def run_evaluation(
    image_path: str,
    name: str,
    description: str,
    price: float,
    category: str,
    claims: list[str],
    brand: str = "Unknown",
    send_msg: Callable[[dict], None] | None = None,
) -> dict:
    def _send(msg: dict) -> None:
        if send_msg:
            send_msg(msg)

    skip_step2_complete = {"flag": False}

    def on_data_step(step: int, status: str, message: str) -> None:
        if step == 2 and status == "complete":
            skip_step2_complete["flag"] = True
            return
        _send({
            "phase": "data_collection",
            "step": step,
            "step_name": STEP_NAMES[step - 1],
            "agent": STEP_NAMES[step - 1],
            "status": status,
            "message": message,
            "output": None,
        })

    raw_data = collect_evaluation_data(
        image_path=image_path,
        name=name,
        description=description,
        price=price,
        category=category,
        claims=claims,
        brand=brand,
        on_step=on_data_step,
    )

    # Compute deterministic verdict BEFORE the crew runs
    predetermined_verdict, predetermined_confidence = compute_verdict(raw_data)
    raw_data["predetermined_verdict"] = predetermined_verdict
    raw_data["predetermined_confidence"] = predetermined_confidence

    all_similar = raw_data.get("all_similar_products", raw_data.get("similar_products", []))
    if all_similar:
        max_sim = max(p["similarity_score"] for p in all_similar)
        inferred_cat = raw_data.get("inferred_category", "")
        category_groups = raw_data.get("category_groups", [])
        _send({
            "phase": "data_collection",
            "step": 2,
            "step_name": STEP_NAMES[1],
            "agent": STEP_NAMES[1],
            "status": "complete",
            "message": (
                f"Found {len(all_similar)} similar products across {len(category_groups)} categories. "
                f"Detected: {inferred_cat}. Highest similarity: {max_sim:.0%}"
            ),
            "output": json.dumps({
                "similar_products": raw_data["similar_products"],
                "enriched_products": raw_data.get("enriched_products", []),
                "classification": raw_data.get("overlap_classification", ""),
                "category_groups": category_groups,
                "inferred_category": inferred_cat,
            }),
        })

    agent_step_map = {0: 4, 1: 5, 2: 6}
    agent_id_map = {0: "risk", 1: "fin", 2: "synth"}
    task_counter = {"current": 0}
    seen_reasonings: list[str] = []

    def on_task_complete(task_output: Any) -> None:
        idx = task_counter["current"]
        ui_step = agent_step_map.get(idx, idx + 4)
        agent_name = AGENT_NAMES[idx] if idx < len(AGENT_NAMES) else f"Agent {idx + 1}"
        output_raw = task_output.raw if hasattr(task_output, "raw") else str(task_output)

        # Fix financial scenarios for Agent 2 (Financial Modeler, idx=1)
        if idx == 1:
            output_raw = _fix_financial_scenarios(output_raw, price)
            if hasattr(task_output, "raw"):
                task_output.raw = output_raw

        reasoning = extract_reasoning(agent_id_map.get(idx, "risk"), output_raw, raw_data)
        # Small instruction models sometimes echo an earlier agent's REASONING line
        # verbatim (it is present in their context). Fall back to the deterministic
        # sentence for this agent rather than showing the same prose three times.
        if any(_similar_prose(reasoning, prev) for prev in seen_reasonings):
            reasoning = _fallback_reasoning(agent_id_map.get(idx, "risk"), raw_data)
        seen_reasonings.append(reasoning)

        _send({
            "phase": "reasoning",
            "step": ui_step,
            "step_name": STEP_NAMES[ui_step - 1] if ui_step <= len(STEP_NAMES) else agent_name,
            "agent": agent_name,
            "status": "complete",
            "message": f"{agent_name} completed analysis",
            "output": output_raw,
            "reasoning": reasoning,
        })

        task_counter["current"] += 1

        next_idx = task_counter["current"]
        if next_idx < len(AGENT_NAMES):
            next_step = agent_step_map.get(next_idx, next_idx + 4)
            next_agent = AGENT_NAMES[next_idx]
            _send({
                "phase": "reasoning",
                "step": next_step,
                "step_name": STEP_NAMES[next_step - 1] if next_step <= len(STEP_NAMES) else next_agent,
                "agent": next_agent,
                "status": "running",
                "message": f"{next_agent} is analyzing...",
                "output": None,
            })

    _send({
        "phase": "reasoning",
        "step": 4,
        "step_name": STEP_NAMES[3],
        "agent": AGENT_NAMES[0],
        "status": "running",
        "message": f"{AGENT_NAMES[0]} is analyzing...",
        "output": None,
    })

    # Fail fast with a clear message when no valid LLM credential exists, instead of
    # letting CrewAI retry a doomed call (the UI would look stuck).
    from tools.llm_config import assert_ready

    assert_ready()

    crew = create_evaluation_crew(
        raw_data,
        task_callback=on_task_complete,
    )
    result = crew.kickoff()

    agent3_output = result.raw if hasattr(result, "raw") else str(result)

    # Deterministic verdict override -- ALWAYS applied.
    # The LLM synthesizes reasoning but the verdict is not negotiable.
    verdict = raw_data["predetermined_verdict"]
    confidence = raw_data["predetermined_confidence"]
    inferred = raw_data.get("inferred_category", "")
    sub = raw_data.get("submission", {})
    sat = raw_data.get("category_saturation", {})
    total_skus = sat.get("total_skus_in_category", 0)
    overlap = raw_data.get("overlap_classification", "")

    # Try to extract Agent 3's reasoning and details
    reason_1 = _extract_field(agent3_output, "REASON_1")
    reason_2 = _extract_field(agent3_output, "REASON_2")
    reason_3 = _extract_field(agent3_output, "REASON_3")
    suggested_retail = _extract_field(agent3_output, "SUGGESTED_RETAIL")
    placement = _extract_field(agent3_output, "PLACEMENT")
    rollout = _extract_field(agent3_output, "ROLLOUT")
    replace_skus = _extract_field(agent3_output, "REPLACE_SKUS")
    replacement_net_impact = _extract_field(agent3_output, "REPLACEMENT_NET_IMPACT")

    # Fallback reasons if Agent 3's output didn't parse
    if not reason_1:
        if verdict == "DECLINE":
            reason_1 = (f"The {inferred} category already has {total_skus} SKUs with {overlap} "
                        f"to existing products -- the shelf does not need another similar product.")
            reason_2 = ("High similarity to multiple existing products means this product would "
                        "cannibalize current assortment without adding incremental value.")
            reason_3 = ("Adding another SKU increases supply chain complexity and shelf management cost "
                        "without proportional category growth.")
        elif verdict == "MODIFY":
            reason_1 = (f"The product shows overlap with existing {inferred} items but has potential "
                        "if repositioned with clearer differentiation.")
            reason_2 = "Modifications to price, claims, or positioning could reduce cannibalization risk."
            reason_3 = "A limited trial in select stores would validate demand before full authorization."
        else:
            reason_1 = "The product fills a gap in the current assortment."
            reason_2 = "Financial projections show positive incremental category contribution."
            reason_3 = "Market trends support demand for this product type."

    if verdict == "DECLINE":
        suggested_retail = "N/A"
        rollout = "0 stores"
        replace_skus = "NONE"
        replacement_net_impact = "N/A"

    final_output = (
        f"VERDICT: {verdict}\n"
        f"CONFIDENCE: {confidence}%\n"
        f"REASON_1: {reason_1}\n"
        f"REASON_2: {reason_2}\n"
        f"REASON_3: {reason_3}\n"
        f"SUGGESTED_RETAIL: {suggested_retail or 'N/A'}\n"
        f"PLACEMENT: {placement or 'N/A'}\n"
        f"ROLLOUT: {rollout or 'N/A'}\n"
        f"REPLACE_SKUS: {replace_skus or 'NONE'}\n"
        f"REPLACEMENT_NET_IMPACT: {replacement_net_impact or 'N/A'}"
    )

    if verdict == "DECLINE":
        final_output += (
            f"\n\nSUPPLIER FEEDBACK: The {inferred} category is well-served with {total_skus} existing products. "
            f"To gain authorization, {sub.get('name', 'this product')} would need to offer clear differentiation "
            f"that no current product provides -- such as a unique format, novel ingredient, distinct price tier, "
            f"or an underserved sub-segment. Consider resubmitting with stronger differentiation or targeting "
            f"a less saturated category."
        )
    elif verdict == "MODIFY":
        final_output += (
            f"\n\nSUPPLIER FEEDBACK: {sub.get('name', 'This product')} has potential but requires modifications "
            f"before authorization. Please address the conditions above and resubmit for evaluation."
        )

    _send({
        "phase": "done",
        "step": 7,
        "step_name": "Complete",
        "agent": "system",
        "status": "done",
        "message": "Evaluation complete",
        "output": final_output,
    })

    # Save evaluation to history
    try:
        from tools.database_client import save_evaluation
        import uuid

        # Combine ALL task outputs for parsing (risk agent has RISK_RATING, financial has EXPECTED)
        all_outputs = "\n".join(
            t.raw if hasattr(t, "raw") else str(t)
            for t in result.tasks_output
        )

        # Verdict and confidence come from the deterministic final_output
        verdict_m = re.search(r"VERDICT:\s*(AUTHORIZE|DECLINE|MODIFY)", final_output, re.IGNORECASE)
        confidence_m = re.search(r"CONFIDENCE:\s*(\d+)", final_output, re.IGNORECASE)
        revenue_m = re.search(r"EXPECTED[^:]*:\s*\$?([\d,]+(?:\.\d+)?)", all_outputs, re.IGNORECASE)
        risk_m = re.search(r"RISK_RATING:\s*(LOW|MEDIUM|HIGH)", all_outputs, re.IGNORECASE)

        eval_id = str(uuid.uuid4())[:8]
        sub = raw_data.get("submission", {})
        all_sim = raw_data.get("all_similar_products", raw_data.get("similar_products", []))
        max_sim = max((p["similarity_score"] for p in all_sim), default=0)
        expected_rev = 0.0
        if revenue_m:
            try:
                expected_rev = float(revenue_m.group(1).replace(",", ""))
            except ValueError:
                pass
        save_evaluation({
            "id": eval_id,
            "product_name": sub.get("name", ""),
            "brand": sub.get("brand", ""),
            "category": sub.get("category", ""),
            "inferred_category": raw_data.get("inferred_category", ""),
            "price": sub.get("price", 0),
            "claims": sub.get("claims", ""),
            "verdict": verdict_m.group(1).upper() if verdict_m else "",
            "confidence": int(confidence_m.group(1)) if confidence_m else 0,
            "overlap_classification": raw_data.get("overlap_classification", ""),
            "expected_revenue": expected_rev,
            "max_similarity": max_sim,
            "risk_rating": risk_m.group(1).upper() if risk_m else "",
            "image_path": sub.get("image_path", ""),
        })
    except Exception as e:
        print(f"Warning: failed to save evaluation history: {e}")

    return {
        "data_package": raw_data,
        "result": final_output,
        "tasks_output": [
            t.raw if hasattr(t, "raw") else str(t)
            for t in result.tasks_output
        ],
    }


if __name__ == "__main__":
    import time
    from dotenv import load_dotenv

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    load_dotenv(BASE_DIR / ".env")

    test_image = str(BASE_DIR / "data" / "images" / "catalog" / "0857777004195.jpg")

    def print_msg(msg: dict) -> None:
        phase = msg.get("phase", "")
        step = msg.get("step", "")
        status = msg.get("status", "")
        step_name = msg.get("step_name", "")
        message = msg.get("message", "")
        has_output = "yes" if msg.get("output") else "no"
        print(f"  [{phase}] Step {step} ({step_name}) - {status}: {message} [output: {has_output}]")

    print("=" * 60)
    print("ORCHESTRATOR TEST")
    print("=" * 60)

    t0 = time.time()
    result = run_evaluation(
        image_path=test_image,
        name="NatureCrunch Eco-Grain Bites",
        description="Wholesome baked grain bites made with ancient grains, chia seeds, and real honey",
        price=5.49,
        category="Organic Snacks",
        claims=["Organic", "Non-GMO", "Plant-Based", "Gluten-Free"],
        brand="NatureCrunch",
        send_msg=print_msg,
    )
    elapsed = time.time() - t0

    print(f"\nTotal time: {elapsed:.1f}s")
    print(f"\nFinal result preview: {result['result'][:300]}...")
