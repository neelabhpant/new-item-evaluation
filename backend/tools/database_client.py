import os
from pathlib import Path

import duckdb

DB_PATH = os.getenv("DUCKDB_PATH", str(Path(__file__).resolve().parent.parent.parent / "data" / "store.db"))


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DB_PATH, read_only=True)


def get_sales_data(sku_list: list[str]) -> list[dict]:
    con = _connect()
    placeholders = ", ".join(["?"] * len(sku_list))
    rows = con.execute(
        f"SELECT s.sku, s.annual_revenue, s.weekly_units, s.velocity_rank, "
        f"s.yoy_growth, s.stores_carrying, s.trend, "
        f"p.price, p.cost, p.margin_pct, p.status, p.shelf_position "
        f"FROM sales_performance s "
        f"JOIN products p ON s.sku = p.sku "
        f"WHERE s.sku IN ({placeholders})",
        sku_list,
    ).fetchall()
    con.close()

    return [
        {
            "sku": r[0],
            "annual_revenue": float(r[1]),
            "weekly_units": int(r[2]),
            "velocity_rank": int(r[3]),
            "yoy_growth": float(r[4]),
            "stores_carrying": int(r[5]),
            "trend": r[6],
            "price": float(r[7]),
            "cost": float(r[8]),
            "margin_pct": float(r[9]),
            "status": r[10],
            "shelf_position": r[11],
        }
        for r in rows
    ]


def get_category_benchmarks(category: str) -> dict | None:
    con = _connect()
    row = con.execute(
        "SELECT category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend "
        "FROM category_benchmarks WHERE category = ?",
        [category],
    ).fetchone()
    con.close()

    if row is None:
        return None

    return {
        "category": row[0],
        "market_size": float(row[1]),
        "yoy_growth": float(row[2]),
        "avg_margin": float(row[3]),
        "avg_price": float(row[4]),
        "sku_count": int(row[5]),
        "top_trend": row[6],
    }


def get_vendor_data(vendor_name: str) -> dict | None:
    con = _connect()
    row = con.execute(
        "SELECT vendor_name, fill_rate, otif_score, compliance_rating, open_chargebacks, relationship_tier "
        "FROM vendor_scorecard WHERE vendor_name = ?",
        [vendor_name],
    ).fetchone()
    con.close()

    if row is None:
        return None

    return {
        "vendor_name": row[0],
        "fill_rate": float(row[1]),
        "otif_score": float(row[2]),
        "compliance_rating": row[3],
        "open_chargebacks": int(row[4]),
        "relationship_tier": row[5],
    }


def get_vendor_data_bulk(vendor_names: list[str]) -> dict[str, dict]:
    if not vendor_names:
        return {}
    con = _connect()
    placeholders = ", ".join(["?"] * len(vendor_names))
    rows = con.execute(
        f"SELECT vendor_name, fill_rate, otif_score, compliance_rating, open_chargebacks, relationship_tier "
        f"FROM vendor_scorecard WHERE vendor_name IN ({placeholders})",
        vendor_names,
    ).fetchall()
    con.close()

    return {
        r[0]: {
            "vendor_name": r[0],
            "fill_rate": float(r[1]),
            "otif_score": float(r[2]),
            "compliance_rating": r[3],
            "open_chargebacks": int(r[4]),
            "relationship_tier": r[5],
        }
        for r in rows
    }


def get_multiple_category_benchmarks(categories: list[str]) -> list[dict]:
    """Query benchmarks for multiple categories at once (for adjacent category analysis)."""
    if not categories:
        return []
    con = _connect()
    placeholders = ", ".join(["?"] * len(categories))
    rows = con.execute(
        f"SELECT category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend "
        f"FROM category_benchmarks WHERE category IN ({placeholders})",
        categories,
    ).fetchall()
    con.close()
    return [
        {
            "category": r[0],
            "market_size": float(r[1]),
            "yoy_growth": float(r[2]),
            "avg_margin": float(r[3]),
            "avg_price": float(r[4]),
            "sku_count": int(r[5]),
            "top_trend": r[6],
        }
        for r in rows
    ]


def get_catalog_summary() -> dict:
    con = _connect()

    total = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    category_rows = con.execute(
        "SELECT category, COUNT(*) as cnt FROM products GROUP BY category ORDER BY cnt DESC"
    ).fetchall()

    brand_rows = con.execute(
        "SELECT brand, COUNT(*) as cnt FROM products GROUP BY brand ORDER BY cnt DESC LIMIT 20"
    ).fetchall()

    benchmark_rows = con.execute(
        "SELECT category, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend "
        "FROM category_benchmarks ORDER BY market_size DESC"
    ).fetchall()

    avg_price = con.execute("SELECT AVG(price) FROM products").fetchone()[0]

    con.close()

    return {
        "total_products": int(total),
        "total_brands": len(brand_rows),
        "total_categories": len(category_rows),
        "avg_price": round(float(avg_price or 0), 2),
        "categories": [{"category": r[0], "count": int(r[1])} for r in category_rows],
        "top_brands": [{"brand": r[0], "count": int(r[1])} for r in brand_rows],
        "benchmarks": [
            {
                "category": r[0],
                "market_size": float(r[1]),
                "yoy_growth": float(r[2]),
                "avg_margin": float(r[3]),
                "avg_price": float(r[4]),
                "sku_count": int(r[5]),
                "top_trend": r[6],
            }
            for r in benchmark_rows
        ],
    }


def get_all_products(category: str | None = None) -> list[dict]:
    con = _connect()

    query = (
        "SELECT p.sku, p.name, p.brand, p.category, p.price, p.status, "
        "s.annual_revenue, s.weekly_units, s.trend, s.yoy_growth "
        "FROM products p LEFT JOIN sales_performance s ON p.sku = s.sku"
    )
    params: list = []
    if category:
        query += " WHERE p.category = ?"
        params.append(category)
    query += " ORDER BY s.annual_revenue DESC"

    rows = con.execute(query, params).fetchall()
    con.close()

    return [
        {
            "sku": r[0],
            "name": r[1],
            "brand": r[2],
            "category": r[3],
            "price": float(r[4]) if r[4] else 0,
            "status": r[5] or "active",
            "annual_revenue": float(r[6]) if r[6] else 0,
            "weekly_units": int(r[7]) if r[7] else 0,
            "trend": r[8] or "stable",
            "yoy_growth": float(r[9]) if r[9] else 0,
        }
        for r in rows
    ]


def _connect_writable() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DB_PATH, read_only=False)


def save_evaluation(evaluation: dict) -> None:
    """Save a completed evaluation to history."""
    con = _connect_writable()
    con.execute(
        """INSERT INTO evaluation_history
           (id, product_name, brand, category, inferred_category, price, claims,
            verdict, confidence, overlap_classification, expected_revenue,
            max_similarity, risk_rating, image_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            evaluation.get("id", ""),
            evaluation.get("product_name", ""),
            evaluation.get("brand", ""),
            evaluation.get("category", ""),
            evaluation.get("inferred_category", ""),
            evaluation.get("price", 0),
            evaluation.get("claims", ""),
            evaluation.get("verdict", ""),
            evaluation.get("confidence", 0),
            evaluation.get("overlap_classification", ""),
            evaluation.get("expected_revenue", 0),
            evaluation.get("max_similarity", 0),
            evaluation.get("risk_rating", ""),
            evaluation.get("image_path", ""),
        ],
    )
    con.close()


def get_evaluations(limit: int = 50, offset: int = 0) -> list[dict]:
    """List evaluation history, most recent first."""
    con = _connect()
    rows = con.execute(
        "SELECT id, timestamp, product_name, brand, category, inferred_category, "
        "price, claims, verdict, confidence, overlap_classification, "
        "expected_revenue, max_similarity, risk_rating, image_path "
        "FROM evaluation_history ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        [limit, offset],
    ).fetchall()
    con.close()
    return [
        {
            "id": r[0],
            "timestamp": str(r[1]),
            "product_name": r[2],
            "brand": r[3],
            "category": r[4],
            "inferred_category": r[5],
            "price": float(r[6]) if r[6] else 0,
            "claims": r[7],
            "verdict": r[8],
            "confidence": int(r[9]) if r[9] else 0,
            "overlap_classification": r[10],
            "expected_revenue": float(r[11]) if r[11] else 0,
            "max_similarity": float(r[12]) if r[12] else 0,
            "risk_rating": r[13],
            "image_path": r[14],
        }
        for r in rows
    ]


def get_evaluation_stats() -> dict:
    """Aggregate stats for evaluation history dashboard."""
    con = _connect()
    total = con.execute("SELECT COUNT(*) FROM evaluation_history").fetchone()[0]
    if total == 0:
        con.close()
        return {"total": 0, "authorize_count": 0, "decline_count": 0, "modify_count": 0, "avg_confidence": 0}
    authorize = con.execute("SELECT COUNT(*) FROM evaluation_history WHERE UPPER(verdict) = 'AUTHORIZE'").fetchone()[0]
    decline = con.execute("SELECT COUNT(*) FROM evaluation_history WHERE UPPER(verdict) = 'DECLINE'").fetchone()[0]
    modify = con.execute("SELECT COUNT(*) FROM evaluation_history WHERE UPPER(verdict) = 'MODIFY'").fetchone()[0]
    avg_conf = con.execute("SELECT AVG(confidence) FROM evaluation_history WHERE confidence > 0").fetchone()[0]
    con.close()
    return {
        "total": int(total),
        "authorize_count": int(authorize),
        "decline_count": int(decline),
        "modify_count": int(modify),
        "avg_confidence": round(float(avg_conf or 0), 1),
    }


if __name__ == "__main__":
    print("=== Sales Data ===")
    sales = get_sales_data(["0857777004195"])
    for s in sales:
        print(f"  {s}")

    print("\n=== Category Benchmarks ===")
    bench = get_category_benchmarks("Protein Bars")
    print(f"  {bench}")

    print("\n=== Vendor Data ===")
    vendor = get_vendor_data("RXBAR")
    print(f"  {vendor}")
