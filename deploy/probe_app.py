"""Stdlib-only probe application used to diagnose Cloudera AI Application startup."""
import os, sys, json, time, http.server, socketserver, pathlib, site
log = pathlib.Path("/home/cdsw/logs"); log.mkdir(parents=True, exist_ok=True)
with open(log / "probe.log", "a") as f:
    f.write(json.dumps({"ts": time.time(), "python": sys.executable, "cwd": os.getcwd(), "argv": sys.argv,
                        "has_file": "__file__" in globals(), "name": __name__, "port": os.getenv("CDSW_APP_PORT"),
                        "workload_pw": bool(os.getenv("WORKLOAD_PASSWORD")), "jwt": os.path.exists("/tmp/jwt")}) + "\n")
port = int(os.environ.get("CDSW_APP_PORT", "8090"))
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(b"probe ok\n")
with socketserver.TCPServer(("0.0.0.0", port), H) as httpd:
    httpd.serve_forever()
