"""CML Job 03: compute CLIP embeddings for the catalog (and load a remote OpenSearch).

  * always: scripts/index_catalog.py --embed-only  -> data/catalog_embeddings.jsonl
  * OPENSEARCH_MODE=external: also create the index and bulk-load it
    (embedded mode loads the index inside the application pod at start instead).
"""

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
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

import index_catalog  # noqa: E402


def main() -> None:
    records = index_catalog.embed_catalog(force="--force" in sys.argv)
    if os.getenv("OPENSEARCH_MODE", "embedded") == "external":
        from tools.opensearch_conn import base_url, wait_ready

        print(f"OPENSEARCH_MODE=external: loading {base_url()} ...")
        if not wait_ready(timeout_s=60):
            raise SystemExit(f"OpenSearch at {base_url()} is not reachable")
        index_catalog.load_catalog(records)
    else:
        print("OPENSEARCH_MODE=embedded: the application loads the index from the cache at start.")


if __name__ == "__main__":
    main()
