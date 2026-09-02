"""Download the catalog product images referenced by data/catalog_products.json.

Reproducible alternative to download_catalog.py (which re-queries the Open Food
Facts search API and may return a different product set): every record in the
committed catalog JSON carries `image_front_url`, so the exact image set that
the metadata describes is fetched into data/images/catalog/{barcode}.jpg.

Usage:
    python scripts/fetch_images.py            # skips images that already exist
    python scripts/fetch_images.py --force    # re-download everything
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image


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
CATALOG_FILE = REPO_ROOT / "data" / "catalog_products.json"
IMAGE_DIR = REPO_ROOT / "data" / "images" / "catalog"
HEADERS = {"User-Agent": "NewItemEval/1.0 (catalog bootstrap)"}


def fetch_one(url: str, dest: Path, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1000:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img.save(dest, format="JPEG", quality=90)
                return True
            if resp.status_code == 404:
                return False
        except (requests.RequestException, OSError):
            pass
        time.sleep(1.5 * attempt)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--delay", type=float, default=0.2, help="seconds between requests")
    args, _ = ap.parse_known_args(argv)

    with open(CATALOG_FILE) as f:
        products = json.load(f)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{len(products)} products in {CATALOG_FILE.relative_to(REPO_ROOT)} -> {IMAGE_DIR.relative_to(REPO_ROOT)}")

    downloaded = skipped = failed = 0
    for i, p in enumerate(products, 1):
        code, url = p.get("code"), p.get("image_front_url")
        if not code or not url:
            failed += 1
            continue
        dest = IMAGE_DIR / f"{code}.jpg"
        if dest.exists() and dest.stat().st_size > 1000 and not args.force:
            skipped += 1
            continue
        if fetch_one(url, dest):
            downloaded += 1
            if downloaded % 25 == 0:
                print(f"  [{i}/{len(products)}] downloaded {downloaded}")
        else:
            failed += 1
            print(f"  FAILED {code} {p.get('product_name', '')[:40]} {url}")
        time.sleep(args.delay)

    total = len(products)
    print(f"\nDone: downloaded={downloaded} skipped={skipped} failed={failed} (of {total})")
    if failed > total * 0.10:
        print("ERROR: more than 10% of images failed to download")
        return 1
    return 0


if __name__ == "__main__":
    # Inside Cloudera AI's kernel any SystemExit (even 0) marks the job failed, so exit only on error.
    _rc = main()
    if _rc:
        sys.exit(_rc)
