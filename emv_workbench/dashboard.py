"""Loopback dashboard backed by the same parser and assertion engine as the CLI."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from .runner import run, PlanError
from .tlv import decode, inventory, DecodeError
from .report import render_html

PACKAGE = Path(__file__).parent


def make_server(port=8765):
    token = secrets.token_hex(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def respond(self, status, body, kind="application/json"):
            if kind == "application/json":
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'nonce-"+token+"'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def host_allowed(self):
            return self.headers.get("Host") in (
                f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.host_allowed():
                return self.respond(403, {"error":"Use the local dashboard address"})
            if self.path == "/":
                page = (PACKAGE / "static/dashboard.html").read_text(encoding="utf-8")
                return self.respond(200, page.replace("__SESSION_TOKEN__",token), "text/html")
            if self.path == "/api/samples":
                return self.respond(200, json.loads((PACKAGE / "samples.json").read_text()))
            self.respond(404, {"error":"Not found"})

        def do_POST(self):
            if not self.host_allowed() or self.headers.get("X-Workbench-Token") != token:
                return self.respond(403, {"error":"Refresh the local dashboard and try again"})
            if self.path not in ("/api/run","/api/decode"):
                return self.respond(404, {"error":"Not found"})
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isdigit():
                    return self.respond(400, {"error":"A single content length is required"})
                length = int(lengths[0])
                if length > 2_000_000:
                    return self.respond(413, {"error":"Input exceeds 2 MB"})
                payload = json.loads(self.rfile.read(length))
                if self.path == "/api/run":
                    report = run(payload)
                    return self.respond(200, {"report":report,"html":render_html(report)})
                if not isinstance(payload,dict) or not isinstance(payload.get("hex"),str):
                    raise PlanError("Provide hexadecimal text")
                self.respond(200, {"inventory":inventory(decode(payload["hex"]))})
            except (DecodeError,PlanError) as exc:
                self.respond(400, {"error":str(exc)})
            except (ValueError,UnicodeError,RecursionError,TypeError,OSError):
                self.respond(400, {"error":"Invalid input; check the JSON structure or hexadecimal text"})
    return ThreadingHTTPServer(("127.0.0.1",port), Handler)


def serve(port=8765):
    server = make_server(port)
    print(f"Workbench dashboard: http://127.0.0.1:{server.server_port}",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
