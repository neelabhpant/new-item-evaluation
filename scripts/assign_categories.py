"""
Assign a category_assigned field to every product in data/catalog_products.json.

First pass: keyword-based primary classifier over product name.
Second pass: rescue pass for items still in "Other Snacks" using brand-aware rules.
Drops items tagged REMOVE (non-snacks).

Usage:
    python scripts/assign_categories.py
"""

import json
import re
from collections import Counter

CATALOG_FILE = "data/catalog_products.json"

PRIMARY_RULES = [
    (r"protein bar|protein", "Protein Bars"),
    (r"granola bar|granola", "Granola Bars"),
    (r"trail mix|nut mix|mixed nuts", "Trail Mix"),
    (r"tortilla chip|tortilla", "Tortilla Chips"),
    (r"potato chip|kettle|lay's|pringles", "Potato Chips"),
    (r"veggie chip|veggie straw|veggie puff", "Veggie Snacks"),
    (r"popcorn", "Popcorn"),
    (r"rice cake|rice crisp", "Rice Cakes"),
    (r"fruit snack|fruit leather|dried fruit|raisin", "Fruit Snacks"),
    (r"energy bar|cliff bar|clif bar", "Energy Bars"),
    (r"pretzel", "Pretzels"),
    (r"cracker|goldfish|cheez", "Crackers"),
    (r"peanut butter cup|chocolate cup", "Chocolate & Candy"),
    (r"dark chocolate|chocolate bar|cocoa", "Chocolate & Candy"),
    (r"yogurt covered|yogurt", "Yogurt Snacks"),
    (r"cheese", "Cheese Snacks"),
    (r"puff|puffed", "Puffed Snacks"),
    (r"nut bar|nut|almond|cashew", "Nut Bars"),
    (r"cookie|biscuit", "Cookies"),
    (r"chip", "Chips"),
    (r"bar", "Snack Bars"),
]

RESCUE_RULES = [
    (r"rxbar|iq bar|clif|david protein", "Protein Bars"),
    (r"power up|deluxe mix|cranberry.*mix|omega.*mix", "Trail Mix"),
    (r"late july|sun chips|harvest snaps|good thins|too good", "Veggie Snacks"),
    (r"smartfood|orville|popping corn", "Popcorn"),
    (r"lay's|pringles|ruffles|cheetos|crunchy flavored", "Potato Chips"),
    (r"rice krispies|rice snaps|rice snack|lundberg|mochi", "Rice Cakes"),
    (r"triscuit|annie.*bunnies|captain.*wafers|lance", "Crackers"),
    (r"nairn|oatcakes|shortbread|walker's|sablé|gerblé", "Cookies"),
    (r"kinder|cadbury|prince.*chocolat|reese's|miniature cups", "Chocolate & Candy"),
    (r"dried mango|dried plum|dried cranberr|craisin|dried fig|dried blueberr|sun-dried|freeze dried|apricot|probiotic", "Fruit Snacks"),
    (r"veggie stix|veggie stick|green pea snack|baked.*pea", "Veggie Snacks"),
    (r"sourdough nibblers|snyder", "Pretzels"),
    (r"brownie", "Snack Bars"),
    (r"cheddar jalap|cheddar.*crunchy", "Chips"),
    (r"trail.?mix|kerne", "Trail Mix"),
    (r"granulated garlic", "REMOVE"),
    (r"tonik|taman|sésame", "Other Snacks"),
]


def assign_primary(name: str) -> str:
    name_lower = name.lower()
    for pattern, category in PRIMARY_RULES:
        if re.search(pattern, name_lower):
            return category
    return "Other Snacks"


def main():
    with open(CATALOG_FILE) as f:
        products = json.load(f)

    # Primary pass
    categorized = 0
    for p in products:
        name = p.get("product_name", "")
        category = assign_primary(name)
        p["category_assigned"] = category
        if category != "Other Snacks":
            categorized += 1

    print(f"Primary pass: categorized {categorized}/{len(products)} products")

    # Rescue pass
    rescued = 0
    removed = 0
    for p in products:
        if p.get("category_assigned") != "Other Snacks":
            continue
        name = f"{p.get('product_name', '')} {p.get('brands', '')}".lower()
        for pattern, category in RESCUE_RULES:
            if re.search(pattern, name):
                if category == "REMOVE":
                    p["category_assigned"] = "REMOVE"
                    removed += 1
                elif category != "Other Snacks":
                    p["category_assigned"] = category
                    rescued += 1
                break

    products = [p for p in products if p.get("category_assigned") != "REMOVE"]

    with open(CATALOG_FILE, "w") as f:
        json.dump(products, f, indent=2)

    cats = Counter(p["category_assigned"] for p in products)
    print(f"\nRescue pass: rescued {rescued}, removed {removed}")
    print(f"Final total: {len(products)} products\n")
    for cat, count in cats.most_common():
        print(f"  {count:3d}  {cat}")


if __name__ == "__main__":
    main()
