"""Seed the retail tables (products, sales, category benchmarks, vendors).

The synthetic numbers are generated in pure Python from data/catalog_products.json
with a fixed seed (Random(42)) so every backend gets identical data:

  python backend/data/init_db.py --backend duckdb               # laptop: data/store.db
  python backend/data/init_db.py --backend impala               # Cloudera: Iceberg tables via Impala
  python backend/data/init_db.py --backend impala --recreate    # drop + rebuild
  python backend/data/init_db.py --if-missing                   # no-op when tables already populated

The backend defaults to the DB_BACKEND environment variable (see backend/tools/db.py).
"""

import argparse
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path


def _repo_root(levels_up: int) -> Path:
    """Repo root whether run as a file or inside Cloudera AI's PBJ kernel (no __file__)."""
    f = globals().get("__file__")
    if f:
        return Path(f).resolve().parents[levels_up]
    cwd = Path.cwd().resolve()
    for p in (cwd, *cwd.parents):
        if (p / "backend" / "main.py").exists():
            return p
    return cwd


BASE_DIR = _repo_root(2)
sys.path.insert(0, str(BASE_DIR / "backend"))

CATALOG_PATH = BASE_DIR / "data" / "catalog_products.json"
DB_PATH = Path(os.getenv("DUCKDB_PATH", str(BASE_DIR / "data" / "store.db")))

CATEGORY_PRICE_RANGES: dict[str, tuple[float, float]] = {
    "Protein Bars": (3.00, 7.00),
    "Energy Bars": (2.50, 5.50),
    "Granola Bars": (2.50, 5.00),
    "Nut Bars": (3.00, 6.00),
    "Snack Bars": (2.50, 5.00),
    "Chocolate & Candy": (2.00, 6.00),
    "Cookies": (3.00, 6.00),
    "Chips": (3.00, 5.00),
    "Potato Chips": (3.00, 5.00),
    "Tortilla Chips": (3.00, 5.50),
    "Veggie Snacks": (3.00, 5.00),
    "Popcorn": (3.00, 5.50),
    "Crackers": (2.50, 5.00),
    "Rice Cakes": (2.50, 4.50),
    "Pretzels": (2.50, 5.00),
    "Trail Mix": (4.00, 8.00),
    "Fruit Snacks": (2.50, 5.00),
    "Cheese Snacks": (3.00, 5.50),
    "Puffed Snacks": (3.00, 5.00),
    "Other Snacks": (2.50, 5.50),
}

CATEGORY_TRENDS: dict[str, tuple[float, float, str]] = {
    "Protein Bars": (5.0, 12.0, "High-protein, clean-label ingredients"),
    "Energy Bars": (2.0, 8.0, "Functional nutrition and adaptogens"),
    "Granola Bars": (-2.0, 5.0, "Low-sugar reformulations"),
    "Nut Bars": (3.0, 10.0, "Simple ingredient lists"),
    "Snack Bars": (1.0, 6.0, "Portion-controlled snacking"),
    "Chocolate & Candy": (-1.0, 4.0, "Premium and dark chocolate"),
    "Cookies": (-2.0, 4.0, "Better-for-you alternatives"),
    "Chips": (1.0, 5.0, "Bold and global flavors"),
    "Potato Chips": (0.0, 4.0, "Kettle-cooked and craft brands"),
    "Tortilla Chips": (2.0, 7.0, "Restaurant-style and grain-free"),
    "Veggie Snacks": (6.0, 15.0, "Plant-based and baked alternatives"),
    "Popcorn": (3.0, 8.0, "Better-for-you and flavored varieties"),
    "Crackers": (-1.0, 4.0, "Seed-based and gluten-free"),
    "Rice Cakes": (1.0, 6.0, "Flavored and protein-added"),
    "Pretzels": (0.0, 5.0, "Filled and seasoned varieties"),
    "Trail Mix": (3.0, 9.0, "High-protein and superfood blends"),
    "Fruit Snacks": (1.0, 6.0, "Real fruit and reduced sugar"),
    "Cheese Snacks": (2.0, 7.0, "Baked and protein-rich options"),
    "Puffed Snacks": (4.0, 10.0, "Chickpea and lentil based puffs"),
    "Other Snacks": (0.0, 5.0, "Multi-serve and variety packs"),
}

CATEGORY_MARKET_SIZE: dict[str, tuple[float, float]] = {
    "Protein Bars": (2.5e9, 4.0e9),
    "Energy Bars": (1.0e9, 2.0e9),
    "Granola Bars": (2.0e9, 3.5e9),
    "Nut Bars": (800e6, 1.5e9),
    "Snack Bars": (500e6, 1.0e9),
    "Chocolate & Candy": (15.0e9, 25.0e9),
    "Cookies": (8.0e9, 12.0e9),
    "Chips": (5.0e9, 8.0e9),
    "Potato Chips": (8.0e9, 12.0e9),
    "Tortilla Chips": (4.0e9, 7.0e9),
    "Veggie Snacks": (1.0e9, 2.5e9),
    "Popcorn": (2.5e9, 4.5e9),
    "Crackers": (6.0e9, 9.0e9),
    "Rice Cakes": (500e6, 1.0e9),
    "Pretzels": (2.0e9, 3.5e9),
    "Trail Mix": (2.0e9, 3.5e9),
    "Fruit Snacks": (2.5e9, 4.0e9),
    "Cheese Snacks": (1.5e9, 3.0e9),
    "Puffed Snacks": (800e6, 1.5e9),
    "Other Snacks": (500e6, 1.5e9),
}

STATUSES = ["active"] * 15 + ["clearance"] * 2 + ["seasonal"] * 2 + ["new"] * 1
SHELF_POSITIONS = ["eye-level"] * 5 + ["top"] * 3 + ["bottom"] * 3 + ["endcap"] * 1
COMPLIANCE_RATINGS = ["Excellent"] * 4 + ["Good"] * 5 + ["Fair"] * 2 + ["Needs Improvement"] * 1
RELATIONSHIP_TIERS = ["Strategic"] * 2 + ["Preferred"] * 4 + ["Standard"] * 5 + ["Probationary"] * 1

# ---------------------------------------------------------------------------
# Schema (portable DDL; Impala adds STORED BY ICEBERG, DuckDB adds PRIMARY KEY)
# ---------------------------------------------------------------------------

SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "products": [
        ("sku", "VARCHAR"), ("name", "VARCHAR"), ("category", "VARCHAR"), ("brand", "VARCHAR"),
        ("price", "DECIMAL(8,2)"), ("cost", "DECIMAL(8,2)"), ("margin_pct", "DECIMAL(5,2)"),
        ("status", "VARCHAR"), ("shelf_position", "VARCHAR"), ("authorized_date", "DATE"),
        ("image_path", "VARCHAR"),
    ],
    "sales_performance": [
        ("sku", "VARCHAR"), ("annual_revenue", "DECIMAL(12,2)"), ("weekly_units", "INTEGER"),
        ("velocity_rank", "INTEGER"), ("yoy_growth", "DECIMAL(5,2)"), ("stores_carrying", "INTEGER"),
        ("trend", "VARCHAR"),
    ],
    "category_benchmarks": [
        ("category", "VARCHAR"), ("market_size", "DECIMAL(14,2)"), ("yoy_growth", "DECIMAL(5,2)"),
        ("avg_margin", "DECIMAL(5,2)"), ("avg_price", "DECIMAL(8,2)"), ("sku_count", "INTEGER"),
        ("top_trend", "VARCHAR"),
    ],
    "vendor_scorecard": [
        ("vendor_name", "VARCHAR"), ("fill_rate", "DECIMAL(5,2)"), ("otif_score", "DECIMAL(5,2)"),
        ("compliance_rating", "VARCHAR"), ("open_chargebacks", "INTEGER"), ("relationship_tier", "VARCHAR"),
    ],
    "evaluation_history": [
        ("id", "VARCHAR"), ("timestamp", "TIMESTAMP"), ("product_name", "VARCHAR"), ("brand", "VARCHAR"),
        ("category", "VARCHAR"), ("inferred_category", "VARCHAR"), ("price", "DECIMAL(8,2)"),
        ("claims", "VARCHAR"), ("verdict", "VARCHAR"), ("confidence", "INTEGER"),
        ("overlap_classification", "VARCHAR"), ("expected_revenue", "DECIMAL(12,2)"),
        ("max_similarity", "DECIMAL(5,4)"), ("risk_rating", "VARCHAR"), ("image_path", "VARCHAR"),
    ],
}
PRIMARY_KEYS = {"products": "sku", "sales_performance": "sku", "category_benchmarks": "category",
                "vendor_scorecard": "vendor_name", "evaluation_history": "id"}
SEED_TABLES = ["products", "sales_performance", "category_benchmarks", "vendor_scorecard"]


def create_table_sql(table: str, backend: str, qualified: str, if_not_exists: bool = True) -> str:
    cols = SCHEMAS[table]
    ine = "IF NOT EXISTS " if if_not_exists else ""
    if backend == "impala":
        # Impala types: STRING instead of VARCHAR, INT, no DEFAULT / PRIMARY KEY on Iceberg.
        # Column names are backtick-quoted because `timestamp` is a reserved word.
        col_defs = ", ".join(
            f"`{c}` {t.replace('VARCHAR', 'STRING').replace('INTEGER', 'INT')}" for c, t in cols
        )
        return f"CREATE TABLE {ine}{qualified} ({col_defs}) STORED BY ICEBERG"
    col_defs = ", ".join(
        f'"{c}" {t}' + (" PRIMARY KEY" if c == PRIMARY_KEYS[table] else "")
        + (" DEFAULT CURRENT_TIMESTAMP" if table == "evaluation_history" and c == "timestamp" else "")
        for c, t in cols
    )
    return f"CREATE TABLE {ine}{qualified} ({col_defs})"


# ---------------------------------------------------------------------------
# Synthetic data generators (unchanged logic, no I/O)
# ---------------------------------------------------------------------------

def load_catalog() -> list[dict]:
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)


def gen_products(catalog: list[dict], rng: random.Random) -> list[tuple]:
    base_date = date(2020, 1, 1)
    rows = []
    for p in catalog:
        sku = p.get("code", "")
        name = p.get("product_name", "Unknown")
        category = p.get("category_assigned", "Other Snacks")
        brand = p.get("brands", "Unknown")
        image_path = p.get("local_image_path", "")

        price_lo, price_hi = CATEGORY_PRICE_RANGES.get(category, (2.50, 5.50))
        price = round(rng.uniform(price_lo, price_hi), 2)
        cost_pct = rng.uniform(0.40, 0.60)
        cost = round(price * cost_pct, 2)
        margin_pct = round((1 - cost_pct) * 100, 2)

        status = rng.choice(STATUSES)
        shelf_position = rng.choice(SHELF_POSITIONS)
        days_offset = rng.randint(0, 1500)
        authorized_date = base_date + timedelta(days=days_offset)

        rows.append((sku, name, category, brand, price, cost, margin_pct, status, shelf_position, authorized_date, image_path))
    return rows


def gen_sales_performance(catalog: list[dict], rng: random.Random, product_prices: dict[str, float]) -> list[tuple]:
    category_skus: dict[str, list[tuple[str, int]]] = {}
    rows_pre_rank = []

    for p in catalog:
        sku = p.get("code", "")
        category = p.get("category_assigned", "Other Snacks")

        weekly_units = rng.randint(50, 2000)
        price = product_prices.get(sku, 4.00)
        noise = rng.uniform(0.85, 1.15)
        annual_revenue = round(weekly_units * price * 52 * noise, 2)

        cat_growth_lo, cat_growth_hi = CATEGORY_TRENDS.get(category, (0.0, 5.0))[:2]
        yoy_growth = round(rng.uniform(cat_growth_lo - 10, cat_growth_hi + 5), 2)
        yoy_growth = max(-15.0, min(30.0, yoy_growth))

        if yoy_growth > 5:
            trend = "growing"
        elif yoy_growth < -2:
            trend = "declining"
        else:
            trend = "stable"

        stores_carrying = rng.randint(200, 4000)

        rows_pre_rank.append((sku, annual_revenue, weekly_units, 0, yoy_growth, stores_carrying, trend))
        category_skus.setdefault(category, []).append((sku, weekly_units))

    velocity_ranks: dict[str, int] = {}
    for cat, skus in category_skus.items():
        sorted_skus = sorted(skus, key=lambda x: x[1], reverse=True)
        for rank, (sku, _) in enumerate(sorted_skus, 1):
            velocity_ranks[sku] = rank

    return [(r[0], r[1], r[2], velocity_ranks[r[0]], r[4], r[5], r[6]) for r in rows_pre_rank]


def gen_category_benchmarks(categories: set[str], rng: random.Random, category_sku_counts: dict[str, int]) -> list[tuple]:
    rows = []
    for cat in sorted(categories):
        size_lo, size_hi = CATEGORY_MARKET_SIZE.get(cat, (500e6, 1.5e9))
        market_size = round(rng.uniform(size_lo, size_hi), 2)

        growth_lo, growth_hi, top_trend = CATEGORY_TRENDS.get(cat, (0.0, 5.0, "General snacking growth"))
        yoy_growth = round(rng.uniform(growth_lo, growth_hi), 2)

        price_lo, price_hi = CATEGORY_PRICE_RANGES.get(cat, (2.50, 5.50))
        avg_price = round((price_lo + price_hi) / 2, 2)
        avg_margin = round(rng.uniform(35.0, 55.0), 2)

        rows.append((cat, market_size, yoy_growth, avg_margin, avg_price, category_sku_counts.get(cat, 0), top_trend))
    return rows


def gen_vendor_scorecard(vendors: set[str], rng: random.Random) -> list[tuple]:
    rows = []
    for vendor in sorted(vendors):
        fill_rate = round(rng.uniform(85.0, 99.5), 2)
        otif_score = round(rng.uniform(80.0, 99.0), 2)
        compliance_rating = rng.choice(COMPLIANCE_RATINGS)
        open_chargebacks = rng.randint(0, 15)

        if fill_rate > 95 and otif_score > 92:
            tier_choices = ["Strategic", "Preferred"]
        elif fill_rate > 90:
            tier_choices = ["Preferred", "Standard"]
        else:
            tier_choices = ["Standard", "Probationary"]
        relationship_tier = rng.choice(tier_choices)

        rows.append((vendor, fill_rate, otif_score, compliance_rating, open_chargebacks, relationship_tier))
    return rows


def generate_all() -> dict[str, list[tuple]]:
    """Deterministically generate every seed table (same RNG order as the original DuckDB seeder)."""
    rng = random.Random(42)
    catalog = load_catalog()

    categories: set[str] = set()
    vendors: set[str] = set()
    category_sku_counts: dict[str, int] = {}
    for p in catalog:
        cat = p.get("category_assigned", "Other Snacks")
        brand = p.get("brands", "Unknown")
        categories.add(cat)
        vendors.add(brand)
        category_sku_counts[cat] = category_sku_counts.get(cat, 0) + 1

    products = gen_products(catalog, rng)
    product_prices = {r[0]: float(r[4]) for r in products}
    return {
        "products": products,
        "sales_performance": gen_sales_performance(catalog, rng, product_prices),
        "category_benchmarks": gen_category_benchmarks(categories, rng, category_sku_counts),
        "vendor_scorecard": gen_vendor_scorecard(vendors, rng),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _sql_literal(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, date):
        return f"DATE '{v.isoformat()}'"
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def seed_impala(tables: dict[str, list[tuple]], recreate: bool, if_missing: bool, batch: int = 100) -> None:
    from tools import db

    dbname = db.database()
    db.execute(f"CREATE DATABASE IF NOT EXISTS {dbname}")
    for table in SEED_TABLES + ["evaluation_history"]:
        q = db.qualify(table)
        if recreate and table != "evaluation_history":
            db.execute(f"DROP TABLE IF EXISTS {q}")
        db.execute(create_table_sql(table, "impala", q))
        if table == "evaluation_history":
            continue
        rows = tables[table]
        existing = int(db.scalar(f"SELECT COUNT(*) FROM {q}") or 0)
        if existing == len(rows):
            print(f"  {table:20s} already populated ({existing} rows) - skipping")
            continue
        if existing and if_missing:
            print(f"  {table:20s} has {existing} rows (expected {len(rows)}) - leaving as is (--if-missing)")
            continue
        if existing:
            print(f"  {table:20s} has {existing} rows, expected {len(rows)} - truncating")
            db.execute(f"TRUNCATE TABLE {q}")
        cols = ", ".join(f"`{c}`" for c, _ in SCHEMAS[table])
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            values = ", ".join("(" + ", ".join(_sql_literal(v) for v in r) + ")" for r in chunk)
            db.execute(f"INSERT INTO {q} ({cols}) VALUES {values}")
        print(f"  {table:20s} {int(db.scalar(f'SELECT COUNT(*) FROM {q}') or 0)} rows (Iceberg)")


def seed_duckdb(tables: dict[str, list[tuple]], recreate: bool, if_missing: bool) -> None:
    import duckdb

    if DB_PATH.exists():
        if if_missing:
            con = duckdb.connect(str(DB_PATH), read_only=True)
            try:
                n = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            except Exception:
                n = -1
            con.close()
            if n == len(tables["products"]):
                print(f"{DB_PATH} already populated ({n} products) - skipping (--if-missing)")
                return
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    for table in SEED_TABLES:
        con.execute(create_table_sql(table, "duckdb", table, if_not_exists=False))
        rows = tables[table]
        ph = ", ".join(["?"] * len(SCHEMAS[table]))
        con.executemany(f"INSERT INTO {table} VALUES ({ph})", rows)
        print(f"  {table:20s} {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]} rows")
    con.execute(create_table_sql("evaluation_history", "duckdb", "evaluation_history"))
    con.close()
    print(f"Database saved to {DB_PATH}")


def ensure_evaluation_history():
    """Create evaluation_history if it doesn't exist. Safe to call multiple times (app startup)."""
    from tools import db

    backend = db.backend()
    if backend == "impala":
        db.execute(f"CREATE DATABASE IF NOT EXISTS {db.database()}")
        db.execute(create_table_sql("evaluation_history", "impala", db.qualify("evaluation_history")))
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db.execute(create_table_sql("evaluation_history", "duckdb", "evaluation_history"))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["duckdb", "impala"], default=os.getenv("DB_BACKEND", "duckdb"))
    ap.add_argument("--recreate", action="store_true", help="drop and rebuild the seed tables")
    ap.add_argument("--if-missing", action="store_true", help="do nothing when tables are already populated")
    args, _ = ap.parse_known_args(argv)
    os.environ["DB_BACKEND"] = args.backend

    tables = generate_all()
    print(f"Generated seed data from {CATALOG_PATH.name}: "
          + ", ".join(f"{k}={len(v)}" for k, v in tables.items()))
    print(f"Backend: {args.backend}")
    if args.backend == "impala":
        seed_impala(tables, recreate=args.recreate, if_missing=args.if_missing)
    else:
        seed_duckdb(tables, recreate=args.recreate, if_missing=args.if_missing)

    from tools import db
    print("Done:", db.describe())


if __name__ == "__main__":
    main()
