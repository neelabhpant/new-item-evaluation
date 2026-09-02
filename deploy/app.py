"""Cloudera AI Application entry point (also runnable inside a session).

  1. OPENSEARCH_MODE=embedded -> start OpenSearch in this pod and load the catalog index
     OPENSEARCH_MODE=external -> just wait for the configured cluster
  2. DB_BACKEND=duckdb        -> create data/store.db if missing (Impala/Iceberg needs nothing)
  3. run uvicorn on CDSW_APP_PORT (single worker: evaluation state is in-process)

Environment: see .env.example / DEPLOY_CLOUDERA.md. A .env file at the repo root is
loaded but never overrides variables already set by the project.
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
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))


class _Tee:
    """Mirror stdout/stderr into logs/app-<timestamp>.log on project storage, so an
    Application's startup output can be read from a session (the Workbench UI is
    the only other place Application logs are visible)."""

    def __init__(self, stream, path: Path):
        self._stream = stream
        self._file = open(path, "a", buffering=1)

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def fileno(self):
        return self._stream.fileno()

    def isatty(self):
        return False


if os.getenv("APP_LOG_DIR", "logs"):
    import time as _time

    _log_dir = REPO_ROOT / os.getenv("APP_LOG_DIR", "logs")
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_path = _log_dir / f"app-{_time.strftime('%Y%m%d-%H%M%S')}.log"
    sys.stdout = _Tee(sys.stdout, _log_path)
    sys.stderr = _Tee(sys.stderr, _log_path)
    print(f"[app] logging to {_log_path}", flush=True)
    print(f"[app] env: CDSW_APP_PORT={os.getenv('CDSW_APP_PORT')} DB_BACKEND={os.getenv('DB_BACKEND')} "
          f"OPENSEARCH_MODE={os.getenv('OPENSEARCH_MODE')} LLM_PROVIDER={os.getenv('LLM_PROVIDER')} "
          f"WORKLOAD_PASSWORD={'set' if os.getenv('WORKLOAD_PASSWORD') else 'MISSING'} "
          f"jwt={'present' if Path(os.getenv('CML_JWT_PATH', '/tmp/jwt')).exists() else 'MISSING'}", flush=True)
    import site as _site

    print(f"[app] python={sys.executable} {sys.version.split()[0]} user_site={_site.getusersitepackages()} "
          f"enabled={_site.ENABLE_USER_SITE} cwd={os.getcwd()}", flush=True)

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - diagnostics for the Application pod
    import traceback

    traceback.print_exc()
    print("[app] FATAL: python-dotenv not importable; dependencies missing for this runtime? "
          "Run deploy/install_deps.py with the same runtime.", flush=True)
    raise

load_dotenv(REPO_ROOT / ".env")
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


def prepare_opensearch() -> None:
    mode = os.getenv("OPENSEARCH_MODE", "embedded")
    if mode == "embedded":
        from deploy.opensearch import embedded

        embedded.start()
        embedded.ensure_index_loaded()
    else:
        from tools.opensearch_conn import base_url, wait_ready

        print(f"[app] waiting for external OpenSearch at {base_url()} ...", flush=True)
        if not wait_ready(timeout_s=90):
            print(f"[app] WARNING: OpenSearch at {base_url()} not reachable; evaluations will fail", flush=True)


def prepare_database() -> None:
    from tools import db

    if db.backend() == "duckdb":
        from data.init_db import main as init_db

        if not Path(db.duckdb_path()).exists():
            print("[app] seeding DuckDB ...", flush=True)
            init_db(["--backend", "duckdb", "--if-missing"])
    print(f"[app] tabular backend: {db.describe()}", flush=True)


def main() -> None:
    prepare_opensearch()
    prepare_database()

    from tools import llm_config

    print(f"[app] llm: {llm_config.describe()}", flush=True)

    port = int(os.getenv("PORT") or os.getenv("CDSW_APP_PORT") or 8001)
    # The Cloudera AI engine listens on <pod-ip>:$CDSW_APP_PORT itself and forwards to
    # localhost, so the app must bind 127.0.0.1 (binding 0.0.0.0 fails with "address in use").
    host = os.getenv("APP_HOST", "127.0.0.1")
    print(f"[app] starting uvicorn on {host}:{port}", flush=True)
    # Run uvicorn as a child process: Cloudera AI executes this script inside an IPython
    # kernel whose asyncio loop is already running, so uvicorn.run() cannot be used here.
    import signal
    import subprocess

    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", host, "--port", str(port),
           "--workers", "1", "--log-level", "info", "--timeout-keep-alive", "75"]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT / "backend"), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def _forward_term(signum, frame):
        proc.terminate()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _forward_term)
        except (ValueError, OSError):
            pass
    try:
        for line in proc.stdout:  # forward to the kernel's stdout (UI logs) and the tee file
            print(line.rstrip("\n"), flush=True)
    finally:
        rc = proc.wait()
        print(f"[app] uvicorn exited with code {rc}", flush=True)
        if rc and rc > 0:  # negative = killed by a signal during a normal stop
            raise SystemExit(rc)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        raise
