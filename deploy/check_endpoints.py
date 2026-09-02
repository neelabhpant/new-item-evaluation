"""Connectivity check for the Cloudera services this app depends on.

  python deploy/check_endpoints.py            # LLM + OpenSearch + tabular backend
  python deploy/check_endpoints.py --list     # also list Cloudera AI Inference endpoints

Run this first when something breaks (expired workload token, stopped endpoint,
suspended warehouse, unreachable OpenSearch).
"""

import json
import os
import sys
import time
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

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")


def list_caii_endpoints() -> None:
    import requests
    from tools.llm_config import resolve_api_key

    try:
        import cmlapi

        apps = cmlapi.default_client().list_ml_serving_apps().apps or []
    except Exception as e:
        print(f"  cannot list AI Inference clusters via cmlapi: {e}")
        return
    for app in apps:
        dom = app.cluster_domain
        print(f"  AI Inference cluster {app.app_name} ({dom})")
        r = requests.post(f"https://{dom}/api/v1alpha1/listEndpoints",
                          json={"namespace": "serving-default"},
                          headers={"Authorization": f"Bearer {resolve_api_key()}"}, timeout=30)
        for e in r.json().get("endpoints", []):
            if e.get("state") == "Running":
                print(f"    - {e['name']:40s} {e.get('model_name', ''):45s} {e.get('url', '')}")


def check_llm() -> bool:
    from tools import llm_config

    print("LLM:", json.dumps(llm_config.describe()))
    try:
        s = llm_config.settings()
        client = llm_config.openai_client()
        t = time.time()
        r = client.chat.completions.create(
            model=s["model"], max_tokens=20, temperature=0,
            messages=[{"role": "user", "content": "Reply with exactly: REASONING: ok"}],
        )
        print(f"  chat OK in {time.time() - t:.1f}s -> {r.choices[0].message.content!r}")
        stream = client.chat.completions.create(
            model=s["model"], max_tokens=10, stream=True,
            messages=[{"role": "user", "content": "Say hi"}],
        )
        n = sum(1 for c in stream if c.choices and c.choices[0].delta.content)
        print(f"  streaming OK ({n} chunks)")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def check_opensearch() -> bool:
    from tools import opensearch_conn

    d = opensearch_conn.describe()
    d["plugins_knn"] = any("knn" in p for p in opensearch_conn.plugins())
    print("OpenSearch:", json.dumps(d))
    return bool(d.get("reachable"))


def check_db() -> bool:
    from tools import db

    d = db.describe()
    print("Tabular:", json.dumps(d))
    return bool(d.get("ok"))


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_caii_endpoints()
    ok = all([check_llm(), check_opensearch(), check_db()])
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)
