"""CML Job wrapper for deploy/build_frontend.sh."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
    sys.exit(subprocess.call(["bash", str(root / "deploy" / "build_frontend.sh")]))
