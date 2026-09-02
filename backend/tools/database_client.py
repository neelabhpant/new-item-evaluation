"""Tabular retail data: sales, benchmarks, vendors and evaluation history.

Storage is selected by DB_BACKEND (see tools.db):
  * duckdb  – embedded file (laptop / fallback)
  * impala  – Iceberg tables in the Cloudera Data Lake via Impala (Cloudera AI)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import db
from tools.db import ident, placeholder, placeholders, qualify

# Kept for backwards compatibility with callers that imported DB_PATH.
DB_PATH = db.duckdb_path()


def _f(v, default=0.0) -> float:
    return float(v) if v is not None else default


def _i(v, default=0) -> int:
    return int(v) if v is not None else default


def get_sales_data(sku_list: list[str]) -> list[dict]:
    if not sku_list:
        return []
    rows = db.query(
        f"SELECT s.sku, s.annual_revenue, s.weekly_units, s.velocity_rank, "
        f"s.yoy_growth, s.stores_carrying, s.trend, "
        f"p.price, p.cost, p.margin_pct, p.status, p.shelf_position "
        f"FROM {qualify('sales_performance')} s "
        f"JOIN {qualify('products')} p ON s.sku = p.sku "
        f"WHERE s.sku IN ({placeholders(len(sku_list))})",
        sku_list,
    )
    return [
        {
            "sku": r[0],
            "annual_revenue": _f(r[1]),
            "weekly_units": _i(r[2]),
            "velocity_rank": _i(r[3]),
            "yoy_growth": _f(r[4]),
            "stores_carrying": _i(r[5]),
            "trend": r[6],
            "price": _f(r[7]),
            "cost": _f(r[8]),
            "margin_pct": _f(r[9]),
            "status": r[10],
            "shelf_position": r[11],
        }
        for r in rows
    ]


def _benchmark_row(row) -> dict:
    return {
        "category": row[0],
        "market_size": _f(row[1]),
        "yoy_growth": _f(row[2]),
        "avg_margin": _f(row[3]),
        "avg_price": _f(row[4]),
        "sku_count": _i(row[5]),
        "top_trend": row[6],
    }


def get_category_benchmarks(category: str) -> dict | None:
    rows = db.query(
        f"SELECT category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend "
        f"FROM {qualify('category_benchmarks')} WHERE category = {placeholder()}",
        [category],
    )
    return _benchmark_row(rows[0]) if rows else None


def _vendor_row(row) -> dict:
    return {
        "vendor_name": row[0],
        "fill_rate": _f(row[1]),
        "otif_score": _f(row[2]),
        "compliance_rating": row[3],
        "open_chargebacks": _i(row[4]),
        "relationship_tier": row[5],
    }


def get_vendor_data(vendor_name: str) -> dict | None:
    rows = db.query(
        f"SELECT vendor_name, fill_rate, otif_score, compliance_rating, open_chargebacks, relationship_tier "
        f"FROM {qualify('vendor_scorecard')} WHERE vendor_name = {placeholder()}",
        [vendor_name],
    )
    return _vendor_row(rows[0]) if rows else None


def get_vendor_data_bulk(vendor_names: list[str]) -> dict[str, dict]:
    if not vendor_names:
        return {}
    rows = db.query(
        f"SELECT vendor_name, fill_rate, otif_score, compliance_rating, open_chargebacks, relationship_tier "
        f"FROM {qualify('vendor_scorecard')} WHERE vendor_name IN ({placeholders(len(vendor_names))})",
        vendor_names,
    )
    return {r[0]: _vendor_row(r) for r in rows}


def get_multiple_category_benchmarks(categories: list[str]) -> list[dict]:
    """Query benchmarks for multiple categories at once (for adjacent category analysis)."""
    if not categories:
        return []
    rows = db.query(
        f"SELECT category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend "
        f"FROM {qualify('category_benchmarks')} WHERE category IN ({placeholders(len(categories))})",
        categories,
    )
    return [_benchmark_row(r) for r in rows]


def get_catalog_summary() -> dict:
    products = qualify("products")
    total = db.scalar(f"SELECT COUNT(*) FROM {products}")
    category_rows = db.query(
        f"SELECT category, COUNT(*) AS cnt FROM {products} GROUP BY category ORDER BY cnt DESC"
    )
    brand_rows = db.query(
        f"SELECT brand, COUNT(*) AS cnt FROM {products} GROUP BY brand ORDER BY cnt DESC LIMIT 20"
    )
    benchmark_rows = db.query(
        f"SELECT category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend "
        f"FROM {qualify('category_benchmarks')} ORDER BY market_size DESC"
    )
    avg_price = db.scalar(f"SELECT AVG(price) FROM {products}")

    return {
        "total_products": _i(total),
        "total_brands": len(brand_rows),
        "total_categories": len(category_rows),
        "avg_price": round(_f(avg_price), 2),
        "categories": [{"category": r[0], "count": _i(r[1])} for r in category_rows],
        "top_brands": [{"brand": r[0], "count": _i(r[1])} for r in brand_rows],
        "benchmarks": [_benchmark_row(r) for r in benchmark_rows],
    }


def get_all_products(category: str | None = None) -> list[dict]:
    query = (
        f"SELECT p.sku, p.name, p.brand, p.category, p.price, p.status, "
        f"s.annual_revenue, s.weekly_units, s.trend, s.yoy_growth "
        f"FROM {qualify('products')} p LEFT JOIN {qualify('sales_performance')} s ON p.sku = s.sku"
    )
    params: list = []
    if category:
        query += f" WHERE p.category = {placeholder()}"
        params.append(category)
    query += " ORDER BY s.annual_revenue DESC"

    rows = db.query(query, params)
    return [
        {
            "sku": r[0],
            "name": r[1],
            "brand": r[2],
            "category": r[3],
            "price": _f(r[4]),
            "status": r[5] or "active",
            "annual_revenue": _f(r[6]),
            "weekly_units": _i(r[7]),
            "trend": r[8] or "stable",
            "yoy_growth": _f(r[9]),
        }
        for r in rows
    ]


def save_evaluation(evaluation: dict) -> None:
    """Save a completed evaluation to history."""
    cols = (
        f"id, {ident('timestamp')}, product_name, brand, category, inferred_category, price, claims, "
        "verdict, confidence, overlap_classification, expected_revenue, "
        "max_similarity, risk_rating, image_path"
    )
    claims = evaluation.get("claims", "")
    if isinstance(claims, (list, tuple)):
        claims = ", ".join(str(c) for c in claims)

    def _s(key: str) -> str:
        return str(evaluation.get(key, "") or "")

    values = [
        _s("id"),
        _s("product_name"),
        _s("brand"),
        _s("category"),
        _s("inferred_category"),
        float(evaluation.get("price", 0) or 0),
        str(claims or ""),
        _s("verdict"),
        int(evaluation.get("confidence", 0) or 0),
        _s("overlap_classification"),
        float(evaluation.get("expected_revenue", 0) or 0),
        float(evaluation.get("max_similarity", 0) or 0),
        _s("risk_rating"),
        _s("image_path"),
    ]
    # Iceberg tables have no column defaults, so the timestamp is set explicitly.
    ph = placeholders(14).split(", ")
    ph.insert(1, "now()" if db.backend() == "impala" else "CURRENT_TIMESTAMP")
    db.execute(
        f"INSERT INTO {qualify('evaluation_history')} ({cols}) VALUES ({', '.join(ph)})",
        values,
    )


def get_evaluations(limit: int = 50, offset: int = 0) -> list[dict]:
    """List evaluation history, most recent first."""
    rows = db.query(
        f"SELECT id, {ident('timestamp')}, product_name, brand, category, inferred_category, "
        f"price, claims, verdict, confidence, overlap_classification, "
        f"expected_revenue, max_similarity, risk_rating, image_path "
        f"FROM {qualify('evaluation_history')} ORDER BY {ident('timestamp')} DESC "
        f"LIMIT {int(limit)} OFFSET {int(offset)}"
    )
    return [
        {
            "id": r[0],
            "timestamp": str(r[1]),
            "product_name": r[2],
            "brand": r[3],
            "category": r[4],
            "inferred_category": r[5],
            "price": _f(r[6]),
            "claims": r[7],
            "verdict": r[8],
            "confidence": _i(r[9]),
            "overlap_classification": r[10],
            "expected_revenue": _f(r[11]),
            "max_similarity": _f(r[12]),
            "risk_rating": r[13],
            "image_path": r[14],
        }
        for r in rows
    ]


def get_evaluation_stats() -> dict:
    """Aggregate stats for evaluation history dashboard."""
    hist = qualify("evaluation_history")
    row = db.query(
        f"SELECT COUNT(*), "
        f"SUM(CASE WHEN UPPER(verdict) = 'AUTHORIZE' THEN 1 ELSE 0 END), "
        f"SUM(CASE WHEN UPPER(verdict) = 'DECLINE' THEN 1 ELSE 0 END), "
        f"SUM(CASE WHEN UPPER(verdict) = 'MODIFY' THEN 1 ELSE 0 END), "
        f"AVG(CASE WHEN confidence > 0 THEN confidence END) "
        f"FROM {hist}"
    )
    total = _i(row[0][0]) if row else 0
    if total == 0:
        return {"total": 0, "authorize_count": 0, "decline_count": 0, "modify_count": 0, "avg_confidence": 0}
    r = row[0]
    return {
        "total": total,
        "authorize_count": _i(r[1]),
        "decline_count": _i(r[2]),
        "modify_count": _i(r[3]),
        "avg_confidence": round(_f(r[4]), 1),
    }


if __name__ == "__main__":
    print("Backend:", db.describe())
    print("=== Sales Data ===")
    for s in get_sales_data(["0857777004195"]):
        print(f"  {s}")
    print("\n=== Category Benchmarks ===")
    print(f"  {get_category_benchmarks('Protein Bars')}")
    print("\n=== Vendor Data ===")
    print(f"  {get_vendor_data('RXBAR')}")
    print("\n=== History stats ===")
    print(f"  {get_evaluation_stats()}")
