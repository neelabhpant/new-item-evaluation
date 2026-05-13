"""
Index the product catalog into OpenSearch with CLIP multimodal embeddings.

Reads data/catalog_products.json, generates a combined (image + rich_text)/2
512-dim embedding for each product using CLIP ViT-B/32, and indexes each doc
into the product-catalog index.

Rich text used for the text embedding: name + brand + category_assigned +
top key ingredients (parentheticals stripped, common fillers dropped). This
gives CLIP more semantic signal than name + brand alone.

Prerequisites:
    - OpenSearch running on localhost:9200
    - product-catalog index created (run scripts/create_index.py first)
    - data/catalog_products.json populated (run scripts/download_catalog.py
      and scripts/assign_categories.py first)
    - pip install open-clip-torch torch pillow requests

Usage:
    python scripts/index_catalog.py
"""

import os
import re
import json
import requests
from collections import Counter

import open_clip
import torch
from PIL import Image

OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.environ.get("OPENSEARCH_INDEX", "product-catalog")
CATALOG_FILE = "data/catalog_products.json"

FILLER_WORDS = {
    "natural flavor", "natural flavors", "artificial flavor", "artificial flavors",
    "salt", "water", "sugar", "soy lecithin", "lecithin", "citric acid",
    "color added", "mixed tocopherols", "bht", "tbhq",
}


def extract_key_ingredients(raw: str, max_count: int = 8) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    parts = [p.strip().lower() for p in cleaned.split(",")]
    key = []
    for p in parts:
        p = p.strip(" .")
        if not p or len(p) < 3:
            continue
        if p in FILLER_WORDS:
            continue
        if re.match(r"^[\d.%]+$", p):
            continue
        key.append(p)
        if len(key) >= max_count:
            break
    return " ".join(key)


def build_rich_text(name: str, brand: str, category: str, ingredients_raw: str) -> str:
    key_ingr = extract_key_ingredients(ingredients_raw)
    parts = [name, brand, category]
    if key_ingr:
        parts.append(key_ingr)
    return " ".join(p for p in parts if p)


def main():
    print("Loading CLIP model (ViT-B/32, OpenAI weights)...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    print("Model loaded.\n")

    with open(CATALOG_FILE) as f:
        products = json.load(f)

    print(f"Found {len(products)} products. Indexing into '{INDEX_NAME}'...\n")

    indexed = 0
    failed = 0
    categories_indexed = Counter()

    for i, p in enumerate(products):
        image_path = p.get("local_image_path")
        name = p.get("product_name", "")
        brand = p.get("brands", "") or ""
        category = p.get("category_assigned", "Other Snacks")
        ingredients_raw = p.get("ingredients_text_en", "") or ""

        if not image_path or not os.path.exists(image_path):
            failed += 1
            print(f"  [{i + 1}] SKIP (no image): {name}")
            continue

        try:
            image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)

            rich_text = build_rich_text(name, brand, category, ingredients_raw)
            text_tokens = tokenizer([rich_text])

            with torch.no_grad():
                img_emb = model.encode_image(image)
                img_emb /= img_emb.norm(dim=-1, keepdim=True)
                txt_emb = model.encode_text(text_tokens)
                txt_emb /= txt_emb.norm(dim=-1, keepdim=True)
                combined = (img_emb + txt_emb) / 2
                combined /= combined.norm(dim=-1, keepdim=True)
                embedding = combined.squeeze().tolist()

            doc = {
                "sku": p.get("code", ""),
                "name": name,
                "description": ingredients_raw,
                "category": category,
                "brand": brand,
                "price": 0.0,
                "image_path": image_path,
                "ingredients": ingredients_raw,
                "claims": p.get("labels_en", "") or "",
                "embedding": embedding,
            }

            resp = requests.post(
                f"{OPENSEARCH_URL}/{INDEX_NAME}/_doc/{p['code']}",
                json=doc,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if resp.status_code in (200, 201):
                indexed += 1
                categories_indexed[category] += 1
                if indexed % 25 == 0 or indexed <= 3:
                    print(f"  [{indexed:3d}] {name[:45]:45s} | {category}")
            else:
                failed += 1
                print(f"  FAILED: {name} - {resp.text[:100]}")

        except Exception as e:
            failed += 1
            print(f"  ERROR: {name} - {e}")

    print(f"\n{'=' * 60}")
    print(f"INDEXING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Indexed: {indexed}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {indexed + failed}")
    print(f"\nProducts per category:")
    for cat, count in categories_indexed.most_common():
        print(f"  {count:3d}  {cat}")

    resp = requests.get(
        f"{OPENSEARCH_URL}/{INDEX_NAME}/_count",
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    if resp.status_code == 200:
        os_count = resp.json().get("count", "?")
        print(f"\nOpenSearch index document count: {os_count}")
        if os_count == indexed:
            print("VERIFIED: Index count matches indexed count.")
        else:
            print(f"WARNING: Index has {os_count} docs but indexed {indexed} this run.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
