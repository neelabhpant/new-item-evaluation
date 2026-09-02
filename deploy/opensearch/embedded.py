"""Run a single-node OpenSearch inside a Cloudera AI session / job / application pod.

Why: Cloudera AI pods cannot run Docker, and the demo needs a k-NN capable
OpenSearch without depending on any other service. The official tarball bundles
a JDK and the k-NN plugin, runs as a non-root user, and only needs a few config
lines. It listens on 127.0.0.1:9200, so nothing outside the pod can reach it.

Layout
  OPENSEARCH_HOME      /home/cdsw/.opensearch      distribution (downloaded once, project storage)
  OPENSEARCH_DATA_DIR  /tmp/opensearch-data        pod-local data dir (Lucene locks + NFS don't mix)
  OPENSEARCH_VERSION   2.11.0                      same version as the laptop docker-compose
  OPENSEARCH_JAVA_OPTS -Xms1g -Xmx1g

Because the data dir is ephemeral, the index is reloaded from
data/catalog_embeddings.jsonl at start (seconds, no CLIP needed).

CLI:
  python deploy/opensearch/embedded.py --install-only   # download + extract only (bootstrap job)
  python deploy/opensearch/embedded.py                  # start, load index, keep running
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
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


REPO_ROOT = _repo_root(2)
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

OS_VERSION = os.getenv("OPENSEARCH_VERSION", "2.11.0")
OS_HOME = Path(os.getenv("OPENSEARCH_HOME", str(Path.home() / ".opensearch")))
OS_DATA = Path(os.getenv("OPENSEARCH_DATA_DIR", "/tmp/opensearch-data"))
OS_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
TARBALL_URL = (
    f"https://artifacts.opensearch.org/releases/bundle/opensearch/{OS_VERSION}/"
    f"opensearch-{OS_VERSION}-linux-x64.tar.gz"
)

_proc: subprocess.Popen | None = None


def dist_dir() -> Path:
    return OS_HOME / f"opensearch-{OS_VERSION}"


def ensure_installed() -> Path:
    d = dist_dir()
    if (d / "bin" / "opensearch").exists():
        return d
    OS_HOME.mkdir(parents=True, exist_ok=True)
    tarball = OS_HOME / f"opensearch-{OS_VERSION}-linux-x64.tar.gz"
    print(f"[opensearch] downloading {TARBALL_URL} (~1 GB, one time) ...", flush=True)
    urllib.request.urlretrieve(TARBALL_URL, tarball)
    print("[opensearch] extracting ...", flush=True)
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(OS_HOME)
    tarball.unlink(missing_ok=True)
    if not (d / "bin" / "opensearch").exists():
        raise RuntimeError(f"OpenSearch extraction failed; expected {d}/bin/opensearch")
    print(f"[opensearch] installed at {d}", flush=True)
    return d


def write_config(d: Path) -> None:
    cfg = d / "config" / "opensearch.yml"
    OS_DATA.mkdir(parents=True, exist_ok=True)
    (OS_HOME / "logs").mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "\n".join([
            "cluster.name: nie-embedded",
            "node.name: nie-node",
            "discovery.type: single-node",
            "network.host: 127.0.0.1",
            f"http.port: {OS_PORT}",
            f"path.data: {OS_DATA}",
            f"path.logs: {OS_HOME / 'logs'}",
            "plugins.security.disabled: true",
            "bootstrap.memory_lock: false",
            "",
        ])
    )
    # Stale lock files only exist after an unclean stop of a *previous* process in
    # this same pod; on a fresh pod the data dir is empty.
    for lock in OS_DATA.rglob("node.lock"):
        lock.unlink(missing_ok=True)


def is_running() -> bool:
    from tools.opensearch_conn import cluster_health

    return cluster_health(t=3) is not None


def start(wait_s: float = 180) -> subprocess.Popen | None:
    """Start OpenSearch in the background and wait for yellow/green health."""
    global _proc
    os.environ.setdefault("OPENSEARCH_URL", f"http://127.0.0.1:{OS_PORT}")
    if is_running():
        print("[opensearch] already running", flush=True)
        return None
    d = ensure_installed()
    write_config(d)
    env = {k: v for k, v in os.environ.items() if k not in ("JAVA_HOME", "JAVA_TOOL_OPTIONS")}
    env.update({
        "OPENSEARCH_JAVA_OPTS": os.getenv("OPENSEARCH_JAVA_OPTS", "-Xms1g -Xmx1g"),
        "OPENSEARCH_JAVA_HOME": str(d / "jdk"),
        "OPENSEARCH_PATH_CONF": str(d / "config"),
        "DISABLE_INSTALL_DEMO_CONFIG": "true",
        "DISABLE_SECURITY_PLUGIN": "true",
    })
    log = open(OS_HOME / "logs" / "stdout.log", "ab")
    print(f"[opensearch] starting {d}/bin/opensearch (data={OS_DATA}) ...", flush=True)
    _proc = subprocess.Popen(
        [str(d / "bin" / "opensearch")],
        env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(d),
        start_new_session=True,
    )
    atexit.register(stop)

    def _on_term(signum, frame):  # an Application stop sends SIGTERM; take OpenSearch down too
        stop()
        sys.exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_term)
        except (ValueError, OSError):  # not on the main thread
            pass

    from tools.opensearch_conn import wait_ready

    if not wait_ready(timeout_s=wait_s):
        tail = (OS_HOME / "logs" / "stdout.log").read_text(errors="ignore")[-3000:]
        raise RuntimeError(f"OpenSearch did not become ready in {wait_s}s. Log tail:\n{tail}")
    print("[opensearch] ready", flush=True)
    return _proc


def stop() -> None:
    global _proc
    if _proc and _proc.poll() is None:
        print("[opensearch] stopping ...", flush=True)
        try:
            os.killpg(_proc.pid, signal.SIGTERM)
            _proc.wait(timeout=30)
        except Exception:
            try:
                os.killpg(_proc.pid, signal.SIGKILL)
            except Exception:
                pass
    _proc = None


def ensure_index_loaded() -> int:
    """Create the catalog index and bulk-load it from the embeddings cache if needed."""
    from tools.opensearch_conn import doc_count, index_exists
    from index_catalog import load_cache, load_catalog

    cached = load_cache()
    have = doc_count() if index_exists() else 0
    if cached and have == len(cached):
        print(f"[opensearch] index already loaded ({have} docs)", flush=True)
        return have
    if not cached:
        print("[opensearch] WARNING: no embeddings cache; index left empty "
              "(run scripts/index_catalog.py --embed-only)", flush=True)
        return have
    print(f"[opensearch] loading index from cache ({len(cached)} docs; index has {have}) ...", flush=True)
    return load_catalog(cached)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--install-only", action="store_true")
    ap.add_argument("--no-load", action="store_true", help="start without loading the catalog index")
    args, _ = ap.parse_known_args(argv)
    if args.install_only:
        ensure_installed()
        return
    start()
    if not args.no_load:
        ensure_index_loaded()
    from tools.opensearch_conn import plugins, base_url

    print(f"[opensearch] {base_url()} plugins: {', '.join(plugins())}", flush=True)
    print("[opensearch] running; Ctrl-C to stop", flush=True)
    try:
        while _proc and _proc.poll() is None:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        stop()


if __name__ == "__main__":
    main()
