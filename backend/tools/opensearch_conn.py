"""Single place that knows how to reach OpenSearch.

Works unchanged for:
  * OpenSearch embedded in the Cloudera AI Application pod (http://127.0.0.1:9200, no auth)
  * any external OpenSearch 2.x cluster with the k-NN plugin (https, basic auth, private CA)
  * the laptop docker-compose setup (http://localhost:9200)

Environment variables
---------------------
OPENSEARCH_URL          base URL (default http://localhost:9200)
OPENSEARCH_INDEX        index name (default product-catalog)
OPENSEARCH_USER / OPENSEARCH_PASSWORD   basic auth for an external cluster
OPENSEARCH_CA_CERT      path to a CA bundle for https
OPENSEARCH_VERIFY_SSL   true|false (default true; ignored when OPENSEARCH_CA_CERT is set)
OPENSEARCH_TIMEOUT      default request timeout in seconds (default 10)
"""

from __future__ import annotations

import os
import threading
import time

import requests

_session: requests.Session | None = None
_lock = threading.Lock()


def base_url() -> str:
    return os.getenv("OPENSEARCH_URL", "http://localhost:9200").rstrip("/")


def index_name() -> str:
    return os.getenv("OPENSEARCH_INDEX", "product-catalog")


def timeout() -> float:
    return float(os.getenv("OPENSEARCH_TIMEOUT", "10"))


def _build_session() -> requests.Session:
    s = requests.Session()
    user, pw = os.getenv("OPENSEARCH_USER"), os.getenv("OPENSEARCH_PASSWORD")
    if user and pw:
        s.auth = (user, pw)
    ca = os.getenv("OPENSEARCH_CA_CERT")
    if ca:
        s.verify = ca
    else:
        s.verify = os.getenv("OPENSEARCH_VERIFY_SSL", "true").strip().lower() in ("1", "true", "yes")
    s.headers["Content-Type"] = "application/json"
    return s


def get_session() -> requests.Session:
    global _session
    if _session is None:
        with _lock:
            if _session is None:
                _session = _build_session()
    return _session


def reset_session() -> None:
    global _session
    with _lock:
        _session = None


def url(path: str = "") -> str:
    return f"{base_url()}/{path.lstrip('/')}" if path else base_url()


def index_url(path: str = "") -> str:
    p = index_name()
    return url(f"{p}/{path.lstrip('/')}" if path else p)


def ping(t: float | None = None) -> bool:
    try:
        r = get_session().get(url(), timeout=t or timeout())
        return r.status_code == 200
    except requests.RequestException:
        return False


def cluster_health(t: float | None = None) -> dict | None:
    try:
        r = get_session().get(url("_cluster/health"), timeout=t or timeout())
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def wait_ready(timeout_s: float = 180, interval: float = 2.0) -> bool:
    """Block until the cluster answers /_cluster/health with yellow or green."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        h = cluster_health(t=5)
        if h and h.get("status") in ("yellow", "green"):
            return True
        time.sleep(interval)
    return False


def index_exists() -> bool:
    r = get_session().head(index_url(), timeout=timeout())
    return r.status_code == 200


def doc_count() -> int:
    r = get_session().get(index_url("_count"), timeout=timeout())
    if r.status_code != 200:
        return 0
    return int(r.json().get("count", 0))


def get_document(sku: str) -> dict | None:
    """Fetch one catalog document by SKU with the embedding stripped."""
    r = get_session().get(index_url(f"_doc/{sku}"), timeout=timeout())
    if r.status_code != 200:
        return None
    source = r.json().get("_source", {})
    source.pop("embedding", None)
    return source


def bulk(ndjson: str, t: float = 120) -> dict:
    """POST an NDJSON payload to _bulk; raise if OpenSearch reports item errors."""
    r = get_session().post(
        url("_bulk"),
        data=ndjson.encode("utf-8"),
        headers={"Content-Type": "application/x-ndjson"},
        timeout=t,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        failed = [i for i in body.get("items", []) if list(i.values())[0].get("error")]
        sample = failed[0] if failed else {}
        raise RuntimeError(f"_bulk reported {len(failed)} failed items; first: {sample}")
    return body


def refresh() -> None:
    get_session().post(index_url("_refresh"), timeout=timeout())


def plugins() -> list[str]:
    try:
        r = get_session().get(url("_cat/plugins?format=json"), timeout=timeout())
        return sorted({p.get("component", "") for p in r.json()}) if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []


def describe() -> dict:
    """Non-secret summary for /api/health."""
    h = cluster_health(t=3)
    out = {
        "url": base_url(),
        "index": index_name(),
        "mode": os.getenv("OPENSEARCH_MODE", "external"),
        "reachable": h is not None,
    }
    if h:
        out["status"] = h.get("status")
        try:
            out["docs"] = doc_count()
        except requests.RequestException:
            out["docs"] = None
    return out
