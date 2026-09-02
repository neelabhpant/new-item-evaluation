"""Create the product-catalog OpenSearch index with the knn_vector mapping.

Safe by default: if the index already exists it is left untouched. Pass
--recreate (or OPENSEARCH_RECREATE=1) to delete and rebuild it.

Usage:
    python scripts/create_index.py
    python scripts/create_index.py --recreate
"""

import argparse
import os
import sys
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

from tools.opensearch_conn import get_session, index_exists, index_name, index_url, timeout  # noqa: E402

MAPPING = {
    "settings": {
        "index": {
            "knn": True
        }
    },
    "mappings": {
        "properties": {
            "sku": {"type": "keyword"},
            "name": {"type": "text"},
            "description": {"type": "text"},
            "category": {"type": "keyword"},
            "subcategory": {"type": "keyword"},
            "brand": {"type": "keyword"},
            "price": {"type": "float"},
            "image_path": {"type": "keyword"},
            "ingredients": {"type": "text"},
            "claims": {"type": "keyword"},
            "status": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 512,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "lucene",
                },
            },
        }
    },
}


def ensure_index(recreate: bool = False) -> bool:
    """Create the index if needed. Returns True when a new index was created."""
    name = index_name()
    if index_exists():
        if not recreate:
            print(f"Index '{name}' already exists - leaving it (use --recreate to rebuild).")
            return False
        print(f"Index '{name}' already exists. Deleting...")
        resp = get_session().delete(index_url(), timeout=30)
        if resp.status_code not in (200, 404):
            raise RuntimeError(f"Failed to delete index: {resp.status_code} {resp.text}")
        print("  Deleted.")

    print(f"Creating index '{name}' with knn_vector mapping (dim=512, hnsw, cosinesimil, lucene)...")
    resp = get_session().put(index_url(), json=MAPPING, timeout=max(30, timeout()))
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create index: {resp.status_code} {resp.text}")
    print(f"Created. Response: {resp.json()}")
    return True


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recreate", action="store_true",
                    default=os.getenv("OPENSEARCH_RECREATE", "").strip() in ("1", "true", "yes"))
    args, _ = ap.parse_known_args(argv)
    ensure_index(recreate=args.recreate)


if __name__ == "__main__":
    main()
