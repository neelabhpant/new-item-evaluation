"""
Index the product catalog into OpenSearch with CLIP multimodal embeddings.

Two phases, runnable together or separately:

  embed  - read data/catalog_products.json, generate a combined (image + rich_text)/2
           512-dim CLIP ViT-B/32 embedding per product and cache everything in
           data/catalog_embeddings.jsonl (skipped when the cache is already complete).
  load   - bulk-index the cached documents into the OpenSearch index.

The cache makes (re)loading an index cheap: the embedded OpenSearch used on
Cloudera AI rebuilds its index from the cache at application start in seconds,
and a Data Hub / remote cluster can be loaded without re-running CLIP.

Rich text used for the text embedding: name + brand + category_assigned +
top key ingredients (parentheticals stripped, common fillers dropped). This
gives CLIP more semantic signal than name + brand alone.

Prerequisites:
    - data/catalog_products.json + data/images/catalog (scripts/fetch_images.py)
    - for `load`: OpenSearch reachable via OPENSEARCH_URL (index is created if missing)

Usage:
    python scripts/index_catalog.py                 # embed (if needed) + load
    python scripts/index_catalog.py --embed-only    # CLIP only, no OpenSearch needed
    python scripts/index_catalog.py --load-only     # bulk-load from the cache
    python scripts/index_catalog.py --force         # recompute embeddings
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
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


REPO_ROOT = _repo_root(1)
sys.path.insert(0, str(REPO_ROOT / "backend"))

CATALOG_FILE = REPO_ROOT / "data" / "catalog_products.json"
CACHE_FILE = Path(os.getenv("CATALOG_EMBEDDINGS_FILE", str(REPO_ROOT / "data" / "catalog_embeddings.jsonl")))
CLIP_CACHE_DIR = os.getenv("CLIP_CACHE_DIR", str(Path.home() / ".cache" / "clip"))

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



def _resolve_image(p: dict) -> Path | None:
    rel = p.get("local_image_path")
    candidates = []
    if rel:
        candidates.append(REPO_ROOT / rel)
    if p.get("code"):
        candidates.append(REPO_ROOT / "data" / "images" / "catalog" / f"{p['code']}.jpg")
    for c in candidates:
        if c.exists():
            return c
    return None


def build_doc(p: dict) -> dict:
    name = p.get("product_name", "")
    brand = p.get("brands", "") or ""
    category = p.get("category_assigned", "Other Snacks")
    ingredients_raw = p.get("ingredients_text_en", "") or ""
    return {
        "sku": p.get("code", ""),
        "name": name,
        "description": ingredients_raw,
        "category": category,
        "brand": brand,
        "price": 0.0,
        # relative path; the API serves it by basename via /api/images/{filename}
        "image_path": p.get("local_image_path") or f"data/images/catalog/{p.get('code', '')}.jpg",
        "ingredients": ingredients_raw,
        "claims": p.get("labels_en", "") or "",
    }


def load_cache() -> list[dict]:
    if not CACHE_FILE.exists():
        return []
    with open(CACHE_FILE) as f:
        return [json.loads(line) for line in f if line.strip()]


def embed_catalog(force: bool = False) -> list[dict]:
    """Compute CLIP embeddings for every catalog product (cached in CACHE_FILE)."""
    with open(CATALOG_FILE) as f:
        products = json.load(f)
    with_images = [p for p in products if _resolve_image(p)]

    cached = load_cache()
    if cached and not force and len(cached) == len(with_images):
        print(f"Embeddings cache is complete ({len(cached)} products) - skipping CLIP. Use --force to recompute.")
        return cached
    if not with_images:
        raise SystemExit("No catalog images found. Run scripts/fetch_images.py first.")

    import open_clip
    import torch
    from PIL import Image

    print(f"Loading CLIP model (ViT-B/32, OpenAI weights) from cache dir {CLIP_CACHE_DIR}...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai", cache_dir=CLIP_CACHE_DIR
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    print(f"Model loaded. Embedding {len(with_images)} products ({len(products) - len(with_images)} without image skipped)...")

    records = []
    failed = 0
    for i, p in enumerate(with_images, 1):
        image_path = _resolve_image(p)
        try:
            image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
            doc = build_doc(p)
            rich_text = build_rich_text(doc["name"], doc["brand"], doc["category"], doc["ingredients"])
            text_tokens = tokenizer([rich_text])
            with torch.no_grad():
                img_emb = model.encode_image(image)
                img_emb /= img_emb.norm(dim=-1, keepdim=True)
                txt_emb = model.encode_text(text_tokens)
                txt_emb /= txt_emb.norm(dim=-1, keepdim=True)
                combined = (img_emb + txt_emb) / 2
                combined /= combined.norm(dim=-1, keepdim=True)
            records.append({"sku": doc["sku"], "doc": doc, "embedding": combined.squeeze().tolist()})
            if i % 25 == 0 or i <= 3:
                print(f"  [{i:3d}/{len(with_images)}] {doc['name'][:45]:45s} | {doc['category']}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {p.get('product_name', '')} - {e}")

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(records)} embeddings to {CACHE_FILE} ({failed} failed)")
    return records


def load_catalog(records: list[dict] | None = None, batch: int = 100) -> int:
    """Bulk-index cached records into OpenSearch. Creates the index if missing."""
    from tools.opensearch_conn import bulk, doc_count, index_name, refresh
    from create_index import ensure_index

    records = records or load_cache()
    if not records:
        raise SystemExit(f"No embeddings cache at {CACHE_FILE}. Run with --embed-only first.")
    ensure_index(recreate=False)

    name = index_name()
    print(f"Bulk-indexing {len(records)} documents into '{name}'...")
    categories_indexed: Counter = Counter()
    for i in range(0, len(records), batch):
        chunk = records[i:i + batch]
        lines = []
        for r in chunk:
            lines.append(json.dumps({"index": {"_index": name, "_id": r["sku"]}}))
            lines.append(json.dumps({**r["doc"], "embedding": r["embedding"]}))
            categories_indexed[r["doc"]["category"]] += 1
        bulk("\n".join(lines) + "\n")
        print(f"  indexed {min(i + batch, len(records))}/{len(records)}")
    refresh()

    count = doc_count()
    print(f"\n{'=' * 60}\nINDEXING COMPLETE: {count} documents in '{name}'\n{'=' * 60}")
    for cat, n in categories_indexed.most_common():
        print(f"  {n:3d}  {cat}")
    if count != len(records):
        print(f"WARNING: index has {count} docs but {len(records)} were sent.")
    return count


def main(argv: list[str] | None = None) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))  # for `from create_index import ...`
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embed-only", action="store_true")
    ap.add_argument("--load-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="recompute embeddings even if cached")
    args, _ = ap.parse_known_args(argv)

    records = None
    if not args.load_only:
        records = embed_catalog(force=args.force)
    if not args.embed_only:
        load_catalog(records)


if __name__ == "__main__":
    main()
