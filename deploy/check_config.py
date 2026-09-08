"""First AMP task: fail fast when the launch configuration is incomplete.

The Configure Project form cannot enforce a value for variables that have no default,
so this script checks them before the long install step runs. It uses only the
standard library (nothing is installed yet) and runs inside a Cloudera AI session.

  python deploy/check_config.py

Fails (non-zero exit) when LLM_BASE_URL, LLM_MODEL or IMPALA_HOST is empty or was stored
incorrectly by the Configure Project form (some workspace versions save a browser event object instead of
the typed text for fields that start empty). Connectivity problems are reported as
warnings only: the endpoint or warehouse may still be starting, and the later steps
report them precisely.
"""

import json
import os
import socket
import ssl
import urllib.error
import urllib.request

REQUIRED = {
    "LLM_BASE_URL": "OpenAI-compatible base URL of a Cloudera AI Inference chat endpoint "
                    "(endpoint page in the AI Inference UI, without /chat/completions)",
    "LLM_MODEL": "model id reported by the endpoint, e.g. meta/llama-3.1-8b-instruct",
    "IMPALA_HOST": "Impala coordinator host from the Virtual Warehouse's JDBC URL, "
                   "e.g. coordinator-<warehouse>.dw-<env>.cloudera.site",
}


def _token() -> str:
    for var in ("LLM_API_KEY", "CDP_TOKEN"):
        if os.getenv(var):
            return os.environ[var]
    try:
        raw = open(os.getenv("CML_JWT_PATH", "/tmp/jwt")).read().strip()
        return json.loads(raw).get("access_token", "") if raw.startswith("{") else raw
    except (OSError, ValueError):
        return ""


FORM_BUG_MARKERS = ("dispatchConfig", "nativeEvent", "_targetInst")


def _bare_host(value: str) -> str:
    """Same rule as backend/tools/db.py normalize_host (kept inline: nothing is installed yet)."""
    v = value.strip()
    for prefix in ("jdbc:impala://", "jdbc:hive2://", "https://", "http://"):
        if v.lower().startswith(prefix):
            v = v[len(prefix):]
            break
    return v.split("/", 1)[0].split(";", 1)[0].split(":", 1)[0].strip()


def _diagnose(var: str, val: str, hint: str) -> str | None:
    if not val:
        return f"{var} is empty: set it to the {hint}"
    if val.startswith("{") or any(m in val for m in FORM_BUG_MARKERS):
        return (f"{var} holds a browser event object instead of text (a Configure Project form bug); "
                f"set it to the {hint}")
    if var == "LLM_BASE_URL" and not val.startswith(("http://", "https://")):
        return f"{var} must start with http:// or https://; got {val[:60]!r}"
    return None


def main() -> int:
    problems = []
    for var, hint in REQUIRED.items():
        val = os.getenv(var, "").strip()
        shown = val if len(val) < 120 else val[:100] + "..."
        print(f"{var:14s} = {shown or '<empty>'}")
        problem = _diagnose(var, val, hint)
        if problem:
            problems.append(problem)
    if problems:
        print("\nCONFIGURATION INCOMPLETE")
        for p in problems:
            print(" -", p)
        print("\nFix: open Project Settings > Advanced > Environment Variables, replace the value(s) "
              "with the real text, save, then restart the AMP steps from the AMP status page "
              "(or run deploy/install_deps.py and deploy/cml_setup.py --run from a session).")
        return 1

    db_backend = os.getenv("DB_BACKEND", "impala")
    if db_backend == "impala":
        host = _bare_host(os.environ["IMPALA_HOST"])
        port = int(os.getenv("IMPALA_PORT", "443"))
        if host != os.environ["IMPALA_HOST"].strip():
            print(f"IMPALA_HOST     normalized to {host} (a JDBC URL was pasted; that is fine)")
        try:
            with socket.create_connection((host, port), timeout=10):
                print(f"Impala          reachable at {host}:{port}")
        except OSError as e:
            print(f"WARNING: cannot reach {host}:{port} ({e}); the warehouse may be suspended or the host wrong")
        if not (os.getenv("IMPALA_PASSWORD") or os.getenv("WORKLOAD_PASSWORD")):
            print("WARNING: no WORKLOAD_PASSWORD in this pod; set a workload password in the "
                  "Management Console (User Management) before the table job runs")

    base = os.environ["LLM_BASE_URL"].rstrip("/")
    req = urllib.request.Request(base + "/models", headers={"Authorization": f"Bearer {_token()}"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
            ids = [m.get("id") for m in json.loads(r.read()).get("data", [])]
            print(f"LLM endpoint    reachable; models: {ids}")
            if os.environ["LLM_MODEL"] not in ids:
                print(f"WARNING: LLM_MODEL {os.environ['LLM_MODEL']!r} is not in the endpoint's model list")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as e:
        print(f"WARNING: could not list models at {base} ({e}); check the URL and that the endpoint is Running")

    print("\nConfiguration check passed.")
    return 0


if __name__ == "__main__":
    # A SystemExit(0) would mark the task failed inside the Cloudera AI kernel; exit only on error.
    _rc = main()
    if _rc:
        raise SystemExit(_rc)
