"""
Download a snack-product catalog from Open Food Facts.

Writes images to data/images/catalog/{barcode}.jpg and metadata to
data/catalog_products.json. Each record includes a local_image_path
pointing at the downloaded image so the downstream indexing script can
load it.

Usage:
    python scripts/download_catalog.py
"""

import os
import json
import time
import requests

IMAGE_DIR = "data/images/catalog"
METADATA_FILE = "data/catalog_products.json"
BASE_URL = "https://world.openfoodfacts.org/cgi/search.pl"
HEADERS = {"User-Agent": "NewItemEval/1.0"}

CATEGORIES = [
    "protein bar",
    "granola bar",
    "trail mix",
    "organic chips",
    "veggie chips",
    "popcorn",
    "rice cakes",
    "fruit snacks",
    "nut bar",
    "energy bar",
    "potato chips",
    "tortilla chips",
    "crackers",
    "pretzels",
    "dried fruit",
    "peanut butter cups",
    "dark chocolate bar",
    "yogurt covered",
    "cheese crackers",
    "puffed snacks",
]

FIELDS = (
    "code,product_name,brands,categories_en,"
    "image_front_url,ingredients_text_en,"
    "labels_en,quantity,nutriments"
)


def setup_dirs():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)


def search_category(category, page_size=20):
    params = {
        "search_terms": category,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "countries_tags_en": "united-states",
        "fields": FIELDS,
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code} for '{category}'")
            return []
        return resp.json().get("products", [])
    except requests.exceptions.JSONDecodeError:
        print(f"  Bad JSON response for '{category}' (likely rate limited)")
        return []
    except Exception as e:
        print(f"  Error searching '{category}': {e}")
        return []


def download_image(url, filepath):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def save_metadata(products):
    with open(METADATA_FILE, "w") as f:
        json.dump(products, f, indent=2)


def main():
    setup_dirs()

    products_collected = []
    seen_codes = set()

    print(f"Downloading product catalog across {len(CATEGORIES)} categories...\n")

    for cat_idx, category in enumerate(CATEGORIES):
        print(f"[{cat_idx + 1}/{len(CATEGORIES)}] Searching: {category}")

        results = search_category(category)
        if not results:
            print(f"  No results. Waiting 5s before next category...")
            time.sleep(5)
            continue

        cat_count = 0
        for p in results:
            code = p.get("code")
            name = p.get("product_name", "").strip()
            img_url = p.get("image_front_url")

            if not code or not name or not img_url:
                continue
            if code in seen_codes:
                continue
            if len(name) < 3:
                continue

            filepath = os.path.join(IMAGE_DIR, f"{code}.jpg")
            if download_image(img_url, filepath):
                seen_codes.add(code)
                p["local_image_path"] = filepath
                products_collected.append(p)
                cat_count += 1
                print(f"  [{len(products_collected)}] {name} - {p.get('brands', 'N/A')}")

        print(f"  Got {cat_count} products from '{category}'")
        save_metadata(products_collected)
        time.sleep(2)

    save_metadata(products_collected)

    print(f"\n{'=' * 60}")
    print(f"DONE")
    print(f"Total products: {len(products_collected)}")
    print(f"Images saved to: {IMAGE_DIR}")
    print(f"Metadata saved to: {METADATA_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
