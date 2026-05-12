import json
import random
import os
from datetime import date, timedelta
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = BASE_DIR / "data" / "catalog_products.json"
DB_PATH = BASE_DIR / "data" / "store.db"

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


def load_catalog() -> list[dict]:
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)


def seed_products(con: duckdb.DuckDBPyConnection, catalog: list[dict], rng: random.Random) -> None:
    con.execute("""
        CREATE TABLE products (
            sku VARCHAR PRIMARY KEY,
            name VARCHAR,
            category VARCHAR,
            brand VARCHAR,
            price DECIMAL(8,2),
            cost DECIMAL(8,2),
            margin_pct DECIMAL(5,2),
            status VARCHAR,
            shelf_position VARCHAR,
            authorized_date DATE,
            image_path VARCHAR
        )
    """)

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

    con.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def seed_sales_performance(con: duckdb.DuckDBPyConnection, catalog: list[dict], rng: random.Random, product_prices: dict[str, float]) -> None:
    con.execute("""
        CREATE TABLE sales_performance (
            sku VARCHAR PRIMARY KEY,
            annual_revenue DECIMAL(12,2),
            weekly_units INTEGER,
            velocity_rank INTEGER,
            yoy_growth DECIMAL(5,2),
            stores_carrying INTEGER,
            trend VARCHAR
        )
    """)

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

    rows = []
    for row in rows_pre_rank:
        sku = row[0]
        rows.append((sku, row[1], row[2], velocity_ranks[sku], row[4], row[5], row[6]))

    con.executemany(
        "INSERT INTO sales_performance VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def seed_category_benchmarks(con: duckdb.DuckDBPyConnection, categories: set[str], rng: random.Random, category_sku_counts: dict[str, int]) -> None:
    con.execute("""
        CREATE TABLE category_benchmarks (
            category VARCHAR PRIMARY KEY,
            market_size DECIMAL(14,2),
            yoy_growth DECIMAL(5,2),
            avg_margin DECIMAL(5,2),
            avg_price DECIMAL(8,2),
            sku_count INTEGER,
            top_trend VARCHAR
        )
    """)

    rows = []
    for cat in sorted(categories):
        size_lo, size_hi = CATEGORY_MARKET_SIZE.get(cat, (500e6, 1.5e9))
        market_size = round(rng.uniform(size_lo, size_hi), 2)

        growth_lo, growth_hi, top_trend = CATEGORY_TRENDS.get(cat, (0.0, 5.0, "General snacking growth"))
        yoy_growth = round(rng.uniform(growth_lo, growth_hi), 2)

        price_lo, price_hi = CATEGORY_PRICE_RANGES.get(cat, (2.50, 5.50))
        avg_price = round((price_lo + price_hi) / 2, 2)
        avg_margin = round(rng.uniform(35.0, 55.0), 2)

        sku_count = category_sku_counts.get(cat, 0)

        rows.append((cat, market_size, yoy_growth, avg_margin, avg_price, sku_count, top_trend))

    con.executemany(
        "INSERT INTO category_benchmarks VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def seed_vendor_scorecard(con: duckdb.DuckDBPyConnection, vendors: set[str], rng: random.Random) -> None:
    con.execute("""
        CREATE TABLE vendor_scorecard (
            vendor_name VARCHAR PRIMARY KEY,
            fill_rate DECIMAL(5,2),
            otif_score DECIMAL(5,2),
            compliance_rating VARCHAR,
            open_chargebacks INTEGER,
            relationship_tier VARCHAR
        )
    """)

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

    con.executemany(
        "INSERT INTO vendor_scorecard VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def main() -> None:
    rng = random.Random(42)

    catalog = load_catalog()
    print(f"Loaded {len(catalog)} products from catalog")

    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    con = duckdb.connect(str(DB_PATH))

    categories: set[str] = set()
    vendors: set[str] = set()
    category_sku_counts: dict[str, int] = {}
    for p in catalog:
        cat = p.get("category_assigned", "Other Snacks")
        brand = p.get("brands", "Unknown")
        categories.add(cat)
        vendors.add(brand)
        category_sku_counts[cat] = category_sku_counts.get(cat, 0) + 1

    seed_products(con, catalog, rng)
    print(f"  products:            {con.execute('SELECT COUNT(*) FROM products').fetchone()[0]} rows")

    # Query product prices to pass into sales seeding (revenue = units * price * 52)
    price_rows = con.execute("SELECT sku, price FROM products").fetchall()
    product_prices = {r[0]: float(r[1]) for r in price_rows}

    seed_sales_performance(con, catalog, rng, product_prices)
    print(f"  sales_performance:   {con.execute('SELECT COUNT(*) FROM sales_performance').fetchone()[0]} rows")

    seed_category_benchmarks(con, categories, rng, category_sku_counts)
    print(f"  category_benchmarks: {con.execute('SELECT COUNT(*) FROM category_benchmarks').fetchone()[0]} rows")

    seed_vendor_scorecard(con, vendors, rng)
    print(f"  vendor_scorecard:    {con.execute('SELECT COUNT(*) FROM vendor_scorecard').fetchone()[0]} rows")

    print("\n--- Sample: products ---")
    for row in con.execute("SELECT sku, name, category, brand, price, cost, margin_pct, status FROM products LIMIT 5").fetchall():
        print(f"  {row}")

    print("\n--- Sample: sales_performance ---")
    for row in con.execute("SELECT sku, annual_revenue, weekly_units, velocity_rank, yoy_growth, trend FROM sales_performance LIMIT 5").fetchall():
        print(f"  {row}")

    print("\n--- Sample: category_benchmarks ---")
    for row in con.execute("SELECT * FROM category_benchmarks LIMIT 5").fetchall():
        print(f"  {row}")

    print("\n--- Sample: vendor_scorecard ---")
    for row in con.execute("SELECT * FROM vendor_scorecard LIMIT 5").fetchall():
        print(f"  {row}")

    print(f"\nCategories: {len(categories)}")
    for cat in sorted(categories):
        count = category_sku_counts[cat]
        print(f"  {cat}: {count} SKUs")

    print(f"\nVendors: {len(vendors)}")

    con.close()
    print(f"\nDatabase saved to {DB_PATH}")


def ensure_evaluation_history():
    """Create evaluation_history table if it doesn't exist. Safe to call multiple times."""
    con = duckdb.connect(str(DB_PATH), read_only=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_history (
            id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            product_name VARCHAR,
            brand VARCHAR,
            category VARCHAR,
            inferred_category VARCHAR,
            price DECIMAL(8,2),
            claims VARCHAR,
            verdict VARCHAR,
            confidence INTEGER,
            overlap_classification VARCHAR,
            expected_revenue DECIMAL(12,2),
            max_similarity DECIMAL(5,4),
            risk_rating VARCHAR,
            image_path VARCHAR
        )
    """)
    con.close()


if __name__ == "__main__":
    main()
