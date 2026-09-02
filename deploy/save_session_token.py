"""Copy this pod's valid Cloudera workload token to project storage for the Application.

Cloudera AI injects a workload JWT at /tmp/jwt into session and job pods, but the
Application pod of this project received an HTML error page there instead. The app
therefore falls back to CML_JWT_FALLBACK_PATH (default <repo>/.secrets/jwt.json).
Run this from a Workbench session (or as the scheduled job nie-05-refresh-token):

    python deploy/save_session_token.py

It only overwrites the fallback file when this pod's token is valid, and never
replaces a valid file with an invalid/older one. Tokens live ~10 days; /api/health
shows the remaining lifetime.
"""

import json
import os
import stat
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    f = globals().get("__file__")
    if f:
        return Path(f).resolve().parents[1]
    cwd = Path.cwd().resolve()
    for p in (cwd, *cwd.parents):
        if (p / "backend" / "main.py").exists():
            return p
    return cwd


REPO_ROOT = _repo_root()
sys.path.insert(0, str(REPO_ROOT / "backend"))

from tools.llm_config import _read_token_file, fallback_token_path, jwt_expiry  # noqa: E402


def _note(msg: str) -> None:
    """Print and append to logs/token_refresh.log (job output is only visible in the UI)."""
    print(msg)
    try:
        log_dir = REPO_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "token_refresh.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} pod={os.getenv('CDSW_ENGINE_ID', '?')} {msg}\n")
    except OSError:
        pass


def main() -> int:
    src = Path(os.getenv("CML_JWT_PATH", "/tmp/jwt"))
    dest = fallback_token_path()
    token = _read_token_file(src)
    if not token:
        _note(f"{src} has no valid token in this pod; nothing written (existing {dest} kept).")
        return 1
    exp_new = jwt_expiry(token) or 0
    existing = _read_token_file(dest) if dest.exists() else None
    if existing and (jwt_expiry(existing) or 0) >= exp_new:
        _note(f"{dest} already holds a token that expires no earlier ({time.strftime('%Y-%m-%d %H:%M', time.gmtime(jwt_expiry(existing)))} UTC); nothing to do.")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(dest.parent, stat.S_IRWXU)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps({"access_token": token, "token_type": "Bearer", "saved_at": time.time()}))
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(dest)
    _note(f"Saved workload token to {dest}; expires {time.strftime('%Y-%m-%d %H:%M', time.gmtime(exp_new))} UTC "
          f"({(exp_new - time.time()) / 3600:.0f} h). Running applications pick it up on their next LLM call.")
    return 0


if __name__ == "__main__":
    # Inside Cloudera AI's kernel any SystemExit (even 0) marks the job failed, so exit only on error.
    _rc = main()
    if _rc:
        sys.exit(_rc)
