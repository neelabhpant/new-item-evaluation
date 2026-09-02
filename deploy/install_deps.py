"""Install everything the app needs into the Cloudera AI project (CML Job 01).

Runs in the same runtime family as the application so packages land in
~/.local/lib/python3.x/site-packages on project storage, shared by later jobs
and by the application pod.

Steps (all idempotent):
  1. torch CPU wheel (avoids the ~2.5 GB CUDA wheels a plain `pip install torch` pulls)
  2. backend/requirements.txt
  3. warm the CLIP ViT-B/32 weights cache (CLIP_CACHE_DIR)
  4. download the OpenSearch bundle (embedded mode)
  5. install Node and build the frontend (deploy/build_frontend.sh)
"""

import os
import subprocess
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


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=str(REPO_ROOT), **kw)


def main() -> None:
    py = sys.executable
    skip = set(os.getenv("INSTALL_SKIP", "").split(","))

    if "torch" not in skip:
        run([py, "-m", "pip", "install", "--quiet", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"])
    if "requirements" not in skip:
        run([py, "-m", "pip", "install", "--quiet", "-r", "backend/requirements.txt"])
        # open-clip-torch depends on torchvision; if pip resolved it from PyPI (CUDA build)
        # it will not load against the CPU torch wheel -> force the matching CPU build.
        if subprocess.call([py, "-c", "import torchvision"], cwd=str(REPO_ROOT),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            run([py, "-m", "pip", "install", "--quiet", "--force-reinstall", "--no-deps", "torchvision",
                 "--index-url", "https://download.pytorch.org/whl/cpu"])

    if "clip" not in skip:
        cache = os.getenv("CLIP_CACHE_DIR", str(Path.home() / ".cache" / "clip"))
        run([py, "-c",
             "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai', "
             f"cache_dir={cache!r}); print('CLIP weights cached in', {cache!r})"])

    if "opensearch" not in skip and os.getenv("OPENSEARCH_MODE", "embedded") == "embedded":
        run([py, "deploy/opensearch/embedded.py", "--install-only"])

    if "frontend" not in skip:
        run(["bash", "deploy/build_frontend.sh"])

    print("\nAll dependencies installed.", flush=True)


if __name__ == "__main__":
    main()
