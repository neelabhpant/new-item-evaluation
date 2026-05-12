import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.embedding_client import generate_embedding
from tools.opensearch_client import search_all_products, group_by_category
from tools.database_client import get_sales_data, get_category_benchmarks, get_vendor_data, get_vendor_data_bulk, get_multiple_category_benchmarks


# Minimum similarity for a product to be considered part of an existing category.
# Below this, the product is a genuinely new category not in the catalog.
MIN_CATEGORY_SIMILARITY = 0.86


def infer_category(category_groups: list[dict], user_category: str) -> tuple[str, bool]:
    """Infer the best-matching category from similarity results.
    Returns (category_name, is_new_category).
    If the best match across ALL categories is below MIN_CATEGORY_SIMILARITY,
    the product doesn't belong to any existing category."""
    if user_category and user_category.lower() not in ("auto-detect", "other", "other snacks"):
        return user_category, False
    if not category_groups:
        return user_category or "Uncategorized", True

    # Check if ANY product in the catalog is similar enough
    global_max = max(g["max_similarity"] for g in category_groups)
    if global_max < MIN_CATEGORY_SIMILARITY:
        # Nothing in the catalog is close enough -- genuinely new category
        # Return the closest category as reference, but flag as new
        best_group = max(category_groups, key=lambda g: g["max_similarity"])
        return f"New Category (nearest: {best_group['category']})", True

    # Similarity-weighted vote across categories that meet the threshold
    weighted: dict[str, float] = {}
    for group in category_groups:
        if group["max_similarity"] >= MIN_CATEGORY_SIMILARITY:
            weighted[group["category"]] = sum(
                p["similarity_score"] for p in group["products"]
            )
    if not weighted:
        best_group = max(category_groups, key=lambda g: g["max_similarity"])
        return f"New Category (nearest: {best_group['category']})", True
    return max(weighted, key=weighted.get), False


def classify_overlap(primary_products: list[dict], is_new_category: bool = False) -> str:
    """Classify overlap using only the primary (inferred) category's products."""
    if is_new_category or not primary_products:
        return "White Space"
    max_score = max(p["similarity_score"] for p in primary_products)
    if max_score > 0.88:
        return "High Overlap"
    if max_score > 0.82:
        return "Moderate Overlap"
    return "White Space"


def collect_evaluation_data(
    image_path: str,
    name: str,
    description: str,
    price: float,
    category: str,
    claims: list[str],
    brand: str = "Unknown",
    on_step: Any = None,
) -> dict:
    submission = {
        "name": name,
        "description": description,
        "price": price,
        "category": category,
        "claims": claims,
        "image_path": image_path,
        "brand": brand,
    }

    if on_step:
        on_step(1, "running", "Processing submission...")

    # Text for CLIP: match the catalog indexing format (name + brand + category + claims)
    # Category is included because the catalog was indexed with category in the text.
    # Claims substitute for ingredients (which the catalog has but submissions don't).
    claims_str = " ".join(claims) if claims else ""
    text = f"{name} {brand} {category} {claims_str}".strip()
    embedding = generate_embedding(image_path, text)

    if on_step:
        on_step(1, "complete", "Submission processed")

    if on_step:
        on_step(2, "running", "Searching for similar products...")

    # Cross-category search: always search all products, then group by category
    all_similar = search_all_products(embedding, k=20)
    category_groups = group_by_category(all_similar)
    inferred_category, is_new_category = infer_category(category_groups, category)

    # Primary products = those from the inferred category (for overlap classification)
    if is_new_category:
        primary_products = []
        overlap_classification = "White Space"
    else:
        primary_group = next((g for g in category_groups if g["category"] == inferred_category), None)
        primary_products = primary_group["products"] if primary_group else []
        overlap_classification = classify_overlap(primary_products)

    # For agent analysis: top 10 from the inferred category
    similar_products = primary_products[:10]
    max_sim = max((p["similarity_score"] for p in all_similar), default=0)

    if on_step:
        on_step(
            2,
            "complete",
            f"Found {len(all_similar)} similar products across {len(category_groups)} categories. "
            f"Detected category: {inferred_category}. Highest similarity: {max_sim:.0%}",
        )

    if on_step:
        on_step(3, "running", "Gathering sales and market data...")

    # Query sales data for ALL found products (not just primary category)
    all_skus = [p["sku"] for p in all_similar]
    sales_data = get_sales_data(all_skus) if all_skus else []
    category_benchmarks = get_category_benchmarks(inferred_category) or {}

    # Query benchmarks for all adjacent categories found in similarity results
    adjacent_cats = [g["category"] for g in category_groups if g["category"] != inferred_category]
    adjacent_benchmarks = get_multiple_category_benchmarks(adjacent_cats) if adjacent_cats else []

    vendor_info = get_vendor_data(brand) or {
        "vendor_name": brand,
        "fill_rate": 90.0,
        "otif_score": 85.0,
        "compliance_rating": "Good",
        "open_chargebacks": 0,
        "relationship_tier": "Standard",
    }

    # Build enriched products: merge similarity + sales + vendor per SKU
    competing_brands = list({p["brand"] for p in all_similar if p.get("brand")})
    competing_vendors = get_vendor_data_bulk(competing_brands) if competing_brands else {}

    sales_by_sku = {s["sku"]: s for s in sales_data}
    enriched_products = []
    for p in all_similar:
        sales = sales_by_sku.get(p["sku"], {})
        vendor = competing_vendors.get(p.get("brand", ""), {})
        enriched_products.append({
            # OpenSearch fields
            "sku": p["sku"],
            "name": p["name"],
            "brand": p.get("brand", ""),
            "category": p.get("category", ""),
            "similarity_score": p["similarity_score"],
            "image_path": p.get("image_path", ""),
            "claims": p.get("claims", ""),
            "ingredients": p.get("ingredients", ""),
            # DuckDB sales
            "annual_revenue": sales.get("annual_revenue", 0),
            "weekly_units": sales.get("weekly_units", 0),
            "velocity_rank": sales.get("velocity_rank", 0),
            "yoy_growth": sales.get("yoy_growth", 0),
            "stores_carrying": sales.get("stores_carrying", 0),
            "trend": sales.get("trend", "unknown"),
            "price": sales.get("price", 0),
            "cost": sales.get("cost", 0),
            "margin_pct": sales.get("margin_pct", 0),
            "status": sales.get("status", "unknown"),
            "shelf_position": sales.get("shelf_position", "unknown"),
            # DuckDB vendor
            "vendor_fill_rate": vendor.get("fill_rate", 0),
            "vendor_otif_score": vendor.get("otif_score", 0),
            "vendor_compliance_rating": vendor.get("compliance_rating", "Unknown"),
            "vendor_relationship_tier": vendor.get("relationship_tier", "Unknown"),
            "vendor_open_chargebacks": vendor.get("open_chargebacks", 0),
        })

    # Compute category saturation stats for the inferred category
    category_sku_count = category_benchmarks.get("sku_count", 0)
    primary_enriched = [e for e in enriched_products if e["category"] == inferred_category]
    category_saturation = {
        "total_skus_in_category": category_sku_count,
        "similar_products_found": len(primary_enriched),
        "category_is_full": category_sku_count >= 15,
    }

    if on_step:
        on_step(3, "complete", "Data collection complete")

    return {
        "submission": submission,
        "embedding": embedding,
        "similar_products": similar_products,
        "all_similar_products": all_similar,
        "category_groups": category_groups,
        "inferred_category": inferred_category,
        "is_new_category": is_new_category,
        "overlap_classification": overlap_classification,
        "sales_data": sales_data,
        "category_benchmarks": category_benchmarks,
        "vendor_info": vendor_info,
        "enriched_products": enriched_products,
        "competing_vendors": competing_vendors,
        "adjacent_benchmarks": adjacent_benchmarks,
        "category_saturation": category_saturation,
    }


if __name__ == "__main__":
    import json

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    test_image = BASE_DIR / "data" / "images" / "catalog" / "0857777004195.jpg"

    print("=" * 60)
    print("TESTING DATA COLLECTOR: NatureCrunch Eco-Grain Bites")
    print("=" * 60)

    start = time.time()
    data = collect_evaluation_data(
        image_path=str(test_image),
        name="NatureCrunch Eco-Grain Bites",
        description="Wholesome baked grain bites made with ancient grains, chia seeds, and real honey",
        price=5.49,
        category="Organic Snacks",
        claims=["Organic", "Non-GMO", "Plant-Based", "Gluten-Free"],
        brand="NatureCrunch",
    )
    elapsed = time.time() - start

    print(f"\nCompleted in {elapsed:.1f}s\n")

    print(f"Embedding dimensions: {len(data['embedding'])}")
    print(f"Overlap classification: {data['overlap_classification']}")

    print(f"\nSimilar Products ({len(data['similar_products'])}):")
    for p in data["similar_products"]:
        print(f"  {p['similarity_score']:.2%} | {p['name'][:50]} | {p['brand']} | {p['category']}")

    print(f"\nSales Data ({len(data['sales_data'])} records):")
    for s in data["sales_data"][:5]:
        print(f"  {s['sku']} | ${s['annual_revenue']:,.0f}/yr | {s['weekly_units']} units/wk | {s['trend']}")

    print(f"\nCategory Benchmarks:")
    if data["category_benchmarks"]:
        cb = data["category_benchmarks"]
        print(f"  Market size: ${cb.get('market_size', 0):,.0f}")
        print(f"  YoY growth: {cb.get('yoy_growth', 0):.1f}%")
        print(f"  Avg margin: {cb.get('avg_margin', 0):.1f}%")
        print(f"  Top trend: {cb.get('top_trend', 'N/A')}")
    else:
        print("  No benchmarks found for category")

    print(f"\nVendor Info:")
    vi = data["vendor_info"]
    print(f"  Fill rate: {vi['fill_rate']}%")
    print(f"  OTIF: {vi['otif_score']}%")
    print(f"  Tier: {vi['relationship_tier']}")
